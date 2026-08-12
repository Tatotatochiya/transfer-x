import uuid
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import and_, case, func, nullslast, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.players.models import (
    Contract,
    Player,
    PlayerStatus,
    PlayerVisibility,
)


# ── Status normalization ──────────────────────────────────────────────────────


def has_external_club(player: Player) -> bool:
    """True when a player is attached to a real-world club that isn't on
    TransferX. `team_name` and `world_team_id` are both vendor-sourced; either
    one is proof the player is somebody's, so absence of a TransferX contract
    must not be read as "available"."""
    return bool(player.team_name or player.world_team_id)


async def normalize_player_status(db: AsyncSession, player: Player) -> None:
    """
    Derive player.status and player.current_club_id from active contracts.
    Must be called explicitly after any contract change — no signals.

    ADR 0003: no active TransferX contract does NOT imply free agency. A
    vendor-imported player with a real-world club is EXTERNAL — visible and
    scoutable, but not signable. Only a player with no club anywhere is a true
    FREE_AGENT.
    """
    # Coerce player.id to uuid.UUID — SQLite/aiosqlite may return strings or other types
    player_id = uuid.UUID(str(player.id))

    result = await db.execute(
        select(Contract).where(
            Contract.player_id == player_id,
            Contract.is_active == True,  # noqa: E712
        )
    )
    active = result.scalar_one_or_none()

    was_available = player.status == PlayerStatus.FREE_AGENT or player.open_to_offers

    if active:
        player.status = PlayerStatus.CONTRACTED
        player.current_club_id = active.club_id
    else:
        player.status = (
            PlayerStatus.EXTERNAL if has_external_club(player) else PlayerStatus.FREE_AGENT
        )
        player.current_club_id = None
        player.open_to_offers = False  # flag only meaningful for contracted players

    await db.flush()

    # Fan out PLAYER_AVAILABLE notifications when a player becomes a free agent
    now_available = player.status == PlayerStatus.FREE_AGENT
    if now_available and not was_available:
        try:
            from app.notifications.service import notify_player_available
            await notify_player_available(db, player.id)
        except Exception:
            pass  # Notifications are non-critical; never let them break a transfer


# ── Player CRUD ───────────────────────────────────────────────────────────────


async def create_player(
    db: AsyncSession,
    created_by_user_id: uuid.UUID,
    name: str,
    **kwargs,
) -> Player:
    player = Player(created_by_user_id=created_by_user_id, name=name, **kwargs)
    db.add(player)
    await db.flush()
    return player


async def get_player_by_id(db: AsyncSession, player_id: uuid.UUID) -> Player | None:
    result = await db.execute(
        select(Player)
        .where(Player.id == player_id)
        .options(
            selectinload(Player.current_club),
            selectinload(Player.contracts),
            selectinload(Player.world_team),
        )
    )
    return result.scalar_one_or_none()


async def get_owning_club_id(db: AsyncSession, player: Player) -> uuid.UUID | None:
    """TRA-138: resolve which club may list/accept a transfer for this player.

    `current_club_id` (derived from an active contract) is authoritative when
    set. Otherwise fall back to whichever club created the player record — the
    same fallback `update_my_club_player` already uses for a player with no
    contract row yet.
    """
    if player.current_club_id is not None:
        return player.current_club_id
    if player.created_by_user_id is None:
        return None
    from app.clubs import service as clubs_service
    club = await clubs_service.get_club_by_user_id(db, player.created_by_user_id)
    return club.id if club else None


async def get_active_release_clause(db: AsyncSession, player_id: uuid.UUID) -> Decimal | None:
    """The buyout figure on the player's current contract, if any (item 14)."""
    result = await db.execute(
        select(Contract.release_clause).where(
            Contract.player_id == player_id, Contract.is_active == True,  # noqa: E712
        )
    )
    return result.scalar_one_or_none()


async def trigger_release_clause(db: AsyncSession, player: Player, *, buyer_club_id: uuid.UUID):
    """Item 14: a buyer meeting the release clause bypasses seller consent
    entirely — that's the clause's whole point, per real FIFA release-clause
    rules. Reserves+commits the buyer's budget for the exact clause amount and
    creates the Deal directly, skipping the offer/accept negotiation.

    Scope note: this only tidies up rival OFFERS for the player (mirroring
    item 1). A simultaneous open Sale/auction for the same player is left
    untouched — that overlap is rare enough, and consequential enough
    (compensating displaced bidders), that it deserves its own explicit
    product decision rather than folding it in here.
    """
    from app.deals.models import Deal, DealStage, DealStatus
    from app.offers.service import reject_offers_for_player

    release_clause = await get_active_release_clause(db, player.id)
    if release_clause is None or release_clause <= 0:
        raise ValueError("This player has no active release clause")

    owning_club_id = await get_owning_club_id(db, player)
    if owning_club_id is None:
        raise ValueError("This player has no owning club to buy from")
    if owning_club_id == buyer_club_id:
        raise ValueError("Cannot trigger a release clause against your own player")

    from app import clubs as clubs_module
    await clubs_module.service.reserve_budget(db, club_id=buyer_club_id, transfer_amount=release_clause)
    await clubs_module.service.commit_budget(db, club_id=buyer_club_id, transfer_amount=release_clause)

    deal = Deal(
        buyer_club_id=buyer_club_id,
        seller_club_id=owning_club_id,
        player_id=player.id,
        agreed_fee=release_clause,
        status=DealStatus.IN_PROGRESS,
        stage=DealStage.AGREEMENT,
    )
    db.add(deal)
    await db.flush()

    await reject_offers_for_player(db, player.id)

    from app.audit import service as audit_service
    await audit_service.emit(
        db,
        entity_type="DEAL", entity_id=deal.id,
        action="RELEASE_CLAUSE_TRIGGERED",
        description=f"Release clause of {release_clause:,.0f} triggered — deal {deal.id} created",
    )

    from app.clubs import service as clubs_service
    from app.notifications import service as notif_service
    from app.notifications.models import NotificationType
    buyer_club = await clubs_service.get_club_by_id(db, buyer_club_id)
    buyer_name = buyer_club.name if buyer_club else "A club"
    await notif_service.notify_club(
        db,
        owning_club_id,
        type=NotificationType.RELEASE_CLAUSE_TRIGGERED,
        message=f"{buyer_name} has met {player.name}'s release clause — the transfer proceeds without your consent",
        link=f"/deals/{deal.id}",
        related_player_id=player.id,
    )

    return deal


# Item 13: FIFA/Bosman — pre-contract agreements are only legal in the final
# six months of a contract.
_PRE_CONTRACT_WINDOW_DAYS = 180


async def create_free_agent_deal(db: AsyncSession, player: Player, *, buyer_club_id: uuid.UUID):
    """Item 13: sign a free agent directly — no seller, no fee, no offer/bid
    negotiation pipeline. Downstream (personal terms, paperwork, completion)
    is identical to any other deal."""
    from app.deals.models import Deal, DealStage, DealStatus, DealType
    from app.offers.service import maybe_invite_agent_for_deal, reject_offers_for_player

    # Defence in depth (ADR 0003): the status check alone is what let ~7.8k
    # vendor-imported professionals be signed for nothing, because they were
    # all stored as FREE_AGENT. Re-derive from the club signals too, so a stale
    # or hand-edited status row can't reopen that hole.
    if player.status == PlayerStatus.EXTERNAL or has_external_club(player):
        raise ValueError(
            "This player is under contract to a club outside TransferX and cannot "
            "be signed as a free agent"
        )
    if player.status != PlayerStatus.FREE_AGENT:
        raise ValueError("This player is not a free agent")

    deal = Deal(
        buyer_club_id=buyer_club_id,
        seller_club_id=None,
        player_id=player.id,
        agreed_fee=Decimal("0"),
        deal_type=DealType.FREE_TRANSFER,
        status=DealStatus.IN_PROGRESS,
        stage=DealStage.AGREEMENT,
    )
    db.add(deal)
    await db.flush()

    await reject_offers_for_player(db, player.id)
    await maybe_invite_agent_for_deal(db, deal)

    from app.audit import service as audit_service
    await audit_service.emit(
        db,
        entity_type="DEAL", entity_id=deal.id,
        action="FREE_AGENT_SIGNING_STARTED",
        description=f"Free-agent signing started for {player.name} — deal {deal.id} created",
    )
    return deal


async def create_pre_contract_deal(db: AsyncSession, player: Player, *, buyer_club_id: uuid.UUID):
    """Item 13: a pre-contract (Bosman) agreement — sign now, join for free
    once the current contract expires. Only legal in the contract's final six
    months.

    Scope note: the deal still runs through the normal AGREEMENT → ... →
    COMPLETED pipeline; completion is not auto-deferred to the actual expiry
    date (that needs its own scheduling mechanism — deliberately out of scope
    here). Staff/clubs decide when to execute it, same as any other deal.
    """
    from app.deals.models import Deal, DealStage, DealStatus, DealType
    from app.offers.service import maybe_invite_agent_for_deal, reject_offers_for_player

    current_club_id = await get_owning_club_id(db, player)
    if current_club_id is None:
        raise ValueError("This player has no current club — use free-agent signing instead")
    if current_club_id == buyer_club_id:
        raise ValueError("Cannot pre-contract your own player")

    result = await db.execute(
        select(Contract.end_date).where(
            Contract.player_id == player.id, Contract.is_active == True,  # noqa: E712
        )
    )
    end_date = result.scalar_one_or_none()
    if end_date is None:
        raise ValueError("This player's contract has no end date on record")
    if end_date < date.today():
        raise ValueError("This player's contract has already expired — use free-agent signing instead")
    if end_date - date.today() > timedelta(days=_PRE_CONTRACT_WINDOW_DAYS):
        raise ValueError(
            f"Pre-contract agreements are only permitted in the final "
            f"{_PRE_CONTRACT_WINDOW_DAYS} days of a contract"
        )

    deal = Deal(
        buyer_club_id=buyer_club_id,
        seller_club_id=current_club_id,
        player_id=player.id,
        agreed_fee=Decimal("0"),
        deal_type=DealType.PRE_CONTRACT,
        status=DealStatus.IN_PROGRESS,
        stage=DealStage.AGREEMENT,
    )
    db.add(deal)
    await db.flush()

    await reject_offers_for_player(db, player.id)
    await maybe_invite_agent_for_deal(db, deal)

    from app.audit import service as audit_service
    await audit_service.emit(
        db,
        entity_type="DEAL", entity_id=deal.id,
        action="PRE_CONTRACT_STARTED",
        description=f"Pre-contract agreement started for {player.name} — deal {deal.id} created",
    )
    return deal


async def is_player_verified(db: AsyncSession, player_id: uuid.UUID) -> bool:
    """TRA-89 — True if this player has a claimed, verified PlayerProfile."""
    from app.auth.models import PlayerProfile
    result = await db.execute(
        select(PlayerProfile.verified).where(PlayerProfile.player_id == player_id)
    )
    return bool(result.scalar_one_or_none())


async def player_has_account(db: AsyncSession, player_id: uuid.UUID) -> bool:
    """True if any PlayerProfile (claimed or not) exists for this player."""
    from app.auth.models import PlayerProfile
    result = await db.execute(
        select(PlayerProfile.id).where(PlayerProfile.player_id == player_id)
    )
    return result.scalar_one_or_none() is not None


async def update_player(db: AsyncSession, player: Player, **fields) -> Player:
    for key, value in fields.items():
        if value is not None:
            setattr(player, key, value)
    await db.flush()
    return player


async def list_own_players(
    db: AsyncSession,
    created_by_user_id: uuid.UUID,
    page: int,
    page_size: int,
) -> tuple[list[Player], int]:
    q = (
        select(Player)
        .where(Player.created_by_user_id == created_by_user_id)
        .options(selectinload(Player.current_club))
    )
    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar_one()
    rows = await db.execute(q.order_by(Player.name).offset((page - 1) * page_size).limit(page_size))
    return list(rows.scalars()), total


async def list_market_players(
    db: AsyncSession,
    *,
    is_authenticated: bool,
    position: str | None,
    status: str | None,
    open_to_offers: bool | None,
    search: str | None,
    min_age: int | None,
    max_age: int | None,
    nationality: str | None,
    club_search: str | None,
    # Stats-based filters
    min_goals: int | None = None,
    min_assists: int | None = None,
    min_appearances: int | None = None,
    min_avg_rating: float | None = None,
    min_form_score: float | None = None,
    # Enrichment-based filters
    min_market_value: Decimal | None = None,
    max_market_value: Decimal | None = None,
    contract_expiry_within_months: int | None = None,
    sort_by: str = "name",
    sort_dir: str = "asc",
    page: int = 1,
    page_size: int = 24,
) -> tuple[list[Player], int]:
    from app.clubs.models import Club

    visible = [PlayerVisibility.PUBLIC]
    if is_authenticated:
        visible.append(PlayerVisibility.CLUBS_ONLY)

    q = (
        select(Player)
        .where(Player.visibility.in_(visible))
        .options(selectinload(Player.current_club), selectinload(Player.world_team))
    )
    if position:
        q = q.where(Player.position == position)
    if status:
        q = q.where(Player.status == status)
    if open_to_offers is not None:
        q = q.where(Player.open_to_offers == open_to_offers)
    if search:
        q = q.where(Player.name.ilike(f"%{search}%"))
    if min_age is not None:
        q = q.where(Player.age >= min_age)
    if max_age is not None:
        q = q.where(Player.age <= max_age)
    if nationality:
        q = q.where(Player.nationality.ilike(f"%{nationality}%"))
    if club_search:
        from app.world.models import WorldTeam
        q = (
            q
            .outerjoin(Club, Player.current_club_id == Club.id)
            .outerjoin(WorldTeam, Player.world_team_id == WorldTeam.id)
            .where(
                or_(
                    Club.name.ilike(f"%{club_search}%"),
                    WorldTeam.name.ilike(f"%{club_search}%"),
                    Player.team_name.ilike(f"%{club_search}%"),
                )
            )
        )

    # Stats-based filters: subquery against player_stats
    from app.stats.models import PlayerForm, PlayerStats
    from decimal import Decimal as D

    if any(v is not None for v in [min_goals, min_assists, min_appearances, min_avg_rating]):
        having_clauses = []
        if min_goals is not None:
            having_clauses.append(func.max(PlayerStats.goals) >= min_goals)
        if min_assists is not None:
            having_clauses.append(func.max(PlayerStats.assists) >= min_assists)
        if min_appearances is not None:
            having_clauses.append(func.max(PlayerStats.appearances) >= min_appearances)
        if min_avg_rating is not None:
            having_clauses.append(func.max(PlayerStats.avg_rating) >= D(str(min_avg_rating)))
        stats_sq = (
            select(PlayerStats.player_id)
            .group_by(PlayerStats.player_id)
            .having(and_(*having_clauses))
        )
        q = q.where(Player.id.in_(stats_sq))

    if min_form_score is not None:
        form_sq = select(PlayerForm.player_id).where(
            PlayerForm.form_score >= D(str(min_form_score))
        )
        q = q.where(Player.id.in_(form_sq))

    # Enrichment-based filters
    if min_market_value is not None:
        q = q.where(Player.market_value >= min_market_value)
    if max_market_value is not None:
        q = q.where(Player.market_value <= max_market_value)
    if contract_expiry_within_months is not None:
        cutoff = date.today() + timedelta(days=30 * contract_expiry_within_months)
        q = q.where(Player.contract_expiry.is_not(None), Player.contract_expiry <= cutoff)

    # Sorting — stats columns require a left-join to aggregated stats
    stats_sort_cols = ("goals", "assists", "appearances", "avg_rating")
    if sort_by in stats_sort_cols:
        stats_agg = (
            select(
                PlayerStats.player_id.label("pid"),
                func.max(PlayerStats.goals).label("s_goals"),
                func.max(PlayerStats.assists).label("s_assists"),
                func.max(PlayerStats.appearances).label("s_appearances"),
                func.max(PlayerStats.avg_rating).label("s_avg_rating"),
            )
            .group_by(PlayerStats.player_id)
            .subquery("stats_agg")
        )
        q = q.outerjoin(stats_agg, Player.id == stats_agg.c.pid)
        order_col = {
            "goals": stats_agg.c.s_goals,
            "assists": stats_agg.c.s_assists,
            "appearances": stats_agg.c.s_appearances,
            "avg_rating": stats_agg.c.s_avg_rating,
        }[sort_by]
    elif sort_by == "form_score":
        form_sub = (
            select(
                PlayerForm.player_id.label("pid"),
                PlayerForm.form_score.label("s_form"),
            )
            .subquery("form_sub")
        )
        q = q.outerjoin(form_sub, Player.id == form_sub.c.pid)
        order_col = form_sub.c.s_form
    elif sort_by == "age":
        order_col = Player.age
    elif sort_by == "value":
        # B3: server-side "best value first" — PlayerMarketPage.tsx's own
        # comment documents this as page-local-only today because this param
        # didn't exist ("the /players/market endpoint only accepts
        # name|age|goals|assists|appearances|avg_rating|form_score"). Ranks by
        # fair-value model score minus nominal market_value (desc = most
        # undervalued first); nullslast below handles players with no
        # valuation row or no market_value the same way every other sort here
        # already handles missing data.
        from app.valuation.models import PlayerValuation

        val_rn = (
            select(
                PlayerValuation.player_id.label("pid"),
                PlayerValuation.fair_value.label("s_fair_value"),
                func.row_number()
                .over(
                    partition_by=PlayerValuation.player_id,
                    order_by=PlayerValuation.computed_at.desc(),
                )
                .label("rn"),
            )
            .subquery("val_rn")
        )
        val_latest = (
            select(val_rn.c.pid, val_rn.c.s_fair_value)
            .where(val_rn.c.rn == 1)
            .subquery("val_latest")
        )
        q = q.outerjoin(val_latest, Player.id == val_latest.c.pid)
        order_col = val_latest.c.s_fair_value - Player.market_value
    else:
        order_col = Player.name

    order_expr = nullslast(order_col.desc()) if sort_dir == "desc" else nullslast(order_col.asc())

    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar_one()
    rows = await db.execute(q.order_by(order_expr).offset((page - 1) * page_size).limit(page_size))
    return list(rows.scalars()), total


async def list_club_squad(
    db: AsyncSession,
    club_id: uuid.UUID,
    is_authenticated: bool,
    page: int,
    page_size: int,
) -> tuple[list[Player], int]:
    """Return players whose current_club_id matches, visibility-filtered, sorted by position."""
    visible = [PlayerVisibility.PUBLIC]
    if is_authenticated:
        visible.append(PlayerVisibility.CLUBS_ONLY)

    position_order = case(
        (Player.position == "GK", 0),
        (Player.position == "DEF", 1),
        (Player.position == "MID", 2),
        (Player.position == "FWD", 3),
        else_=4,
    )

    q = (
        select(Player)
        .where(Player.current_club_id == club_id)
        .where(Player.visibility.in_(visible))
        .options(
            selectinload(Player.current_club),
            selectinload(Player.contracts),
            selectinload(Player.world_team),
        )
    )
    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar_one()
    rows = await db.execute(
        q.order_by(position_order, Player.name).offset((page - 1) * page_size).limit(page_size)
    )
    return list(rows.scalars()), total


async def list_world_team_squad(
    db: AsyncSession,
    team_id: uuid.UUID,
    page: int,
    page_size: int,
) -> tuple[list[Player], int]:
    """Return players linked to a world_team_id, sorted by position."""
    position_order = case(
        (Player.position == "GK", 0),
        (Player.position == "DEF", 1),
        (Player.position == "MID", 2),
        (Player.position == "FWD", 3),
        else_=4,
    )
    q = (
        select(Player)
        .where(Player.world_team_id == team_id)
        .where(Player.visibility == PlayerVisibility.PUBLIC)
        .options(selectinload(Player.current_club), selectinload(Player.world_team))
    )
    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar_one()
    rows = await db.execute(
        q.order_by(position_order, Player.name).offset((page - 1) * page_size).limit(page_size)
    )
    return list(rows.scalars()), total


# ── Contract management ───────────────────────────────────────────────────────


async def create_contract(
    db: AsyncSession,
    player: Player,
    club_id: uuid.UUID,
    start_date: date | None = None,
    end_date: date | None = None,
    wage_weekly: Decimal | None = None,
    release_clause: Decimal | None = None,
    notes: str | None = None,
) -> Contract:
    # Coerce player.id to uuid.UUID — SQLite/aiosqlite may return strings or other types
    player_id = uuid.UUID(str(player.id))
    # Deactivate any existing active contracts for this player
    await db.execute(
        update(Contract)
        .where(and_(Contract.player_id == player_id, Contract.is_active == True))  # noqa: E712
        .values(is_active=False)
    )
    contract = Contract(
        player_id=player_id,
        club_id=club_id,
        start_date=start_date,
        end_date=end_date,
        wage_weekly=wage_weekly,
        release_clause=release_clause,
        notes=notes,
        is_active=True,
    )
    db.add(contract)
    await db.flush()
    await normalize_player_status(db, player)
    return contract


async def deactivate_contract(db: AsyncSession, contract: Contract, player: Player) -> None:
    contract.is_active = False
    await db.flush()
    await normalize_player_status(db, player)


def compute_wage_fit(
    player_wage_weekly: Decimal | None, club_wage_remaining_weekly: Decimal | None
) -> "WageFit | None":
    """B4: null when there's nothing to compare — no prospective wage figure
    for the player, or the viewer isn't a club with wage room of its own."""
    from app.players.schemas import WageFit

    if player_wage_weekly is None or club_wage_remaining_weekly is None:
        return None
    room_after = club_wage_remaining_weekly - player_wage_weekly
    return WageFit(fits=room_after >= 0, wage_room_after=room_after)
