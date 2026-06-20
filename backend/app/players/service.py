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


async def normalize_player_status(db: AsyncSession, player: Player) -> None:
    """
    Derive player.status and player.current_club_id from active contracts.
    Must be called explicitly after any contract change — no signals.
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
        player.status = PlayerStatus.FREE_AGENT
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
