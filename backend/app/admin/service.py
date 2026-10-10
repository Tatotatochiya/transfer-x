"""M7 — Admin service layer."""

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.common.filters import apply_date_range


# ── Users ─────────────────────────────────────────────────────────────────────


async def list_users(
    db: AsyncSession,
    *,
    search: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    page: int = 1,
    page_size: int = 30,
):
    from app.auth.models import User

    q = select(User)
    if search:
        like = f"%{search}%"
        q = q.where(or_(User.email.ilike(like), User.first_name.ilike(like), User.last_name.ilike(like)))
    q = apply_date_range(q, User.created_at, date_from, date_to)

    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar_one()
    rows = await db.execute(
        q.order_by(User.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    )
    return list(rows.scalars()), total


async def get_user_by_id(db: AsyncSession, user_id: uuid.UUID):
    from app.auth.models import User

    user_id = uuid.UUID(str(user_id))
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def delete_user(db: AsyncSession, user) -> None:
    await db.delete(user)
    await db.flush()


async def update_user(
    db: AsyncSession,
    user,
    *,
    is_active: bool | None = None,
    is_superuser: bool | None = None,
):
    if is_active is not None:
        user.is_active = is_active
    if is_superuser is not None:
        user.is_superuser = is_superuser
    await db.flush()
    return user


# ── Clubs ─────────────────────────────────────────────────────────────────────


async def list_clubs(
    db: AsyncSession,
    *,
    search: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    page: int = 1,
    page_size: int = 30,
):
    from app.clubs.models import Club

    q = select(Club).options(selectinload(Club.finance))
    if search:
        q = q.where(Club.name.ilike(f"%{search}%"))
    q = apply_date_range(q, Club.created_at, date_from, date_to)

    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar_one()
    rows = await db.execute(
        q.order_by(Club.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    )
    return list(rows.scalars()), total


async def get_club_by_id(db: AsyncSession, club_id: uuid.UUID):
    from app.clubs.models import Club

    club_id = uuid.UUID(str(club_id))
    result = await db.execute(
        select(Club).where(Club.id == club_id).options(selectinload(Club.finance))
    )
    return result.scalar_one_or_none()


async def update_club(
    db: AsyncSession,
    club,
    *,
    name: str | None = None,
    role: str | None = None,
    country: str | None = None,
):
    if name is not None:
        club.name = name
    if role is not None:
        club.role = role
    if country is not None:
        club.country = country
    await db.flush()
    return club


async def delete_club(db: AsyncSession, club) -> None:
    await db.delete(club)
    await db.flush()


async def update_club_finances(
    db: AsyncSession,
    club,
    *,
    transfer_budget_total: Decimal | None = None,
    wage_budget_total_weekly: Decimal | None = None,
):
    """Set a club's budgets. Returns (finance, changes). A budget can't go
    below what is already held, committed or spent against it, which would
    leave the club with a negative amount remaining."""
    from app.clubs.models import ClubFinance

    finance = club.finance
    if finance is None:
        club_id = uuid.UUID(str(club.id))
        finance = ClubFinance(
            club_id=club_id,
            transfer_budget_total=Decimal("0"),
            wage_budget_total_weekly=Decimal("0"),
            transfer_reserved=Decimal("0"),
            wage_reserved_weekly=Decimal("0"),
            transfer_committed=Decimal("0"),
            wage_committed_weekly=Decimal("0"),
        )
        db.add(finance)
        await db.flush()
        # Reload the relationship
        club.finance = finance

    used_transfer = (finance.transfer_reserved or 0) + (finance.transfer_committed or 0) + (finance.transfer_spent or 0)
    used_wage = (finance.wage_reserved_weekly or 0) + (finance.wage_committed_weekly or 0)
    if transfer_budget_total is not None and transfer_budget_total < used_transfer:
        raise ValueError(
            f"The transfer budget can't be below £{used_transfer:,.0f}, the amount already held, committed or spent"
        )
    if wage_budget_total_weekly is not None and wage_budget_total_weekly < used_wage:
        raise ValueError(
            f"The wage budget can't be below £{used_wage:,.0f} a week, the amount already held or committed"
        )
    before = {"transfer_budget_total": finance.transfer_budget_total,
              "wage_budget_total_weekly": finance.wage_budget_total_weekly}
    if transfer_budget_total is not None:
        finance.transfer_budget_total = transfer_budget_total
    if wage_budget_total_weekly is not None:
        finance.wage_budget_total_weekly = wage_budget_total_weekly
    await db.flush()
    from app.admin.audit import changes

    return finance, changes(before, {"transfer_budget_total": finance.transfer_budget_total,
                                     "wage_budget_total_weekly": finance.wage_budget_total_weekly})


# ── User management (extended) ────────────────────────────────────────────────


# ── Club management (extended) ────────────────────────────────────────────────


async def create_club(
    db: AsyncSession,
    user_id: uuid.UUID,
    name: str,
    role: str,
    country: str | None,
    league_name: str | None,
    transfer_budget: Decimal,
    wage_budget: Decimal,
):
    from app.clubs.models import Club, ClubFinance, ClubRole
    from app.auth.models import User

    user_id = uuid.UUID(str(user_id))
    user = await db.get(User, user_id)
    if user is None:
        raise ValueError("User not found")

    existing = (await db.execute(
        select(Club).where(Club.user_id == user_id)
    )).scalar_one_or_none()
    if existing is not None:
        raise ValueError("User already has a club")

    club = Club(
        user_id=user_id,
        name=name,
        role=ClubRole(role),
        country=country,
        league_name=league_name,
    )
    db.add(club)
    await db.flush()

    finance = ClubFinance(
        club_id=club.id,
        transfer_budget_total=transfer_budget,
        wage_budget_total_weekly=wage_budget,
    )
    db.add(finance)
    await db.flush()
    return club


# ── Player management (admin override) ────────────────────────────────────────


async def admin_get_player(db: AsyncSession, player_id: uuid.UUID):
    from app.players.models import Player
    from sqlalchemy.orm import selectinload

    player_id = uuid.UUID(str(player_id))
    result = await db.execute(
        select(Player)
        .where(Player.id == player_id)
        .options(
            selectinload(Player.current_club),
            selectinload(Player.world_team),
            selectinload(Player.contracts),
        )
    )
    return result.scalar_one_or_none()


async def admin_update_player(
    db: AsyncSession,
    player,
    *,
    name: str | None = None,
    age: int | None = None,
    nationality: str | None = None,
    position: str | None = None,
    visibility: str | None = None,
    status: str | None = None,
    open_to_offers: bool | None = None,
    photo_url: str | None = None,
    current_club_id: uuid.UUID | None = None,
    clear_club: bool = False,
):
    from app.players.models import PlayerPosition, PlayerStatus, PlayerVisibility

    if name is not None:
        player.name = name
    if age is not None:
        player.age = age
    if nationality is not None:
        player.nationality = nationality
    if position is not None:
        player.position = PlayerPosition(position)
    if visibility is not None:
        player.visibility = PlayerVisibility(visibility)
    if status is not None:
        player.status = PlayerStatus(status)
    if open_to_offers is not None:
        player.open_to_offers = open_to_offers
    if photo_url is not None:
        player.photo_url = photo_url
    if clear_club:
        player.current_club_id = None
    elif current_club_id is not None:
        player.current_club_id = uuid.UUID(str(current_club_id))
    await db.flush()
    return player


# ── Deal management (admin) ────────────────────────────────────────────────────


async def admin_list_deals(
    db: AsyncSession,
    *,
    status: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    page: int = 1,
    page_size: int = 30,
):
    from app.deals.models import Deal, DealStatus
    from sqlalchemy.orm import selectinload

    q = select(Deal).options(
        selectinload(Deal.player),
        selectinload(Deal.buyer_club),
        selectinload(Deal.seller_club),
    )
    if status:
        q = q.where(Deal.status == DealStatus(status))
    q = apply_date_range(q, Deal.created_at, date_from, date_to)

    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar_one()
    rows = await db.execute(
        q.order_by(Deal.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    )
    return list(rows.scalars()), total


# ── Sale management (admin cancel) ────────────────────────────────────────────


async def admin_cancel_sale(db: AsyncSession, sale, *, reason: str):
    """Cancel an open sale as TransferX staff: the seller's own withdrawal
    (bids and linked offers released, everyone told), with the reason."""
    from app.sales.models import SaleStatus
    from app.sales.service import withdraw_sale

    if sale.status != SaleStatus.OPEN:
        raise ValueError(f"Sale is already {sale.status.value.lower()} — cannot cancel")
    return await withdraw_sale(db, sale, None, staff_reason=reason)


# ── Staff management ──────────────────────────────────────────────────────────


async def list_club_staff_with_users(db: AsyncSession, club_id: uuid.UUID):
    """Return all staff for a club, with user info eagerly loaded."""
    from app.clubs.models import ClubStaff
    from app.auth.models import User
    from sqlalchemy.orm import selectinload

    club_id = uuid.UUID(str(club_id))
    result = await db.execute(
        select(ClubStaff)
        .where(ClubStaff.club_id == club_id)
        .options(selectinload(ClubStaff.user))
        .order_by(ClubStaff.created_at)
    )
    return list(result.scalars())


async def get_staff_by_id(db: AsyncSession, staff_id: uuid.UUID):
    from app.clubs.models import ClubStaff
    from sqlalchemy.orm import selectinload

    staff_id = uuid.UUID(str(staff_id))
    result = await db.execute(
        select(ClubStaff)
        .where(ClubStaff.id == staff_id)
        .options(selectinload(ClubStaff.user))
    )
    return result.scalar_one_or_none()


async def update_staff_role(db: AsyncSession, staff, role: str):
    from app.clubs.models import StaffRole

    staff.role = StaffRole(role)
    await db.flush()
    return staff


async def delete_staff(db: AsyncSession, staff) -> None:
    """Delete both the staff record and the linked user account."""
    from app.auth.models import User

    user_id = staff.user_id
    await db.delete(staff)
    await db.flush()
    user = await db.get(User, user_id)
    if user:
        await db.delete(user)
        await db.flush()


# ── Players (admin — no visibility filter) ────────────────────────────────────


async def admin_list_players(
    db: AsyncSession,
    *,
    search: str | None = None,
    position: str | None = None,
    status: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    page: int = 1,
    page_size: int = 30,
):
    from app.players.models import Player

    q = select(Player).options(
        selectinload(Player.current_club),
        selectinload(Player.world_team),
    )
    if search:
        q = q.where(Player.name.ilike(f"%{search}%"))
    if position:
        q = q.where(Player.position == position)
    if status:
        q = q.where(Player.status == status)
    q = apply_date_range(q, Player.created_at, date_from, date_to)

    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar_one()
    rows = await db.execute(
        q.order_by(Player.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    )
    return list(rows.scalars()), total


# ── Sales (admin — all statuses) ──────────────────────────────────────────────


async def admin_list_sales(
    db: AsyncSession,
    *,
    status: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    page: int = 1,
    page_size: int = 30,
):
    from app.sales.models import Sale

    q = select(Sale).options(
        selectinload(Sale.player),
        selectinload(Sale.seller_club),
    )
    if status:
        q = q.where(Sale.status == status)
    q = apply_date_range(q, Sale.created_at, date_from, date_to)

    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar_one()
    rows = await db.execute(
        q.order_by(Sale.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    )
    return list(rows.scalars()), total


# ── System stats ──────────────────────────────────────────────────────────────


async def get_system_stats(db: AsyncSession) -> dict:
    from app.auth.models import User
    from app.clubs.models import Club
    from app.deals.models import Deal, DealStatus
    from app.offers.models import Offer, OfferStatus
    from app.players.models import Player
    from app.sales.models import Sale, SaleStatus

    total_users = (await db.execute(select(func.count()).select_from(User))).scalar_one()
    total_clubs = (await db.execute(select(func.count()).select_from(Club))).scalar_one()
    total_players = (await db.execute(select(func.count()).select_from(Player))).scalar_one()
    active_sales = (
        await db.execute(
            select(func.count()).select_from(Sale).where(Sale.status == SaleStatus.OPEN)
        )
    ).scalar_one()
    open_offers = (
        await db.execute(
            select(func.count())
            .select_from(Offer)
            .where(Offer.status.in_([OfferStatus.SENT, OfferStatus.COUNTERED]))
        )
    ).scalar_one()
    active_deals = (
        await db.execute(
            select(func.count())
            .select_from(Deal)
            .where(Deal.status == DealStatus.IN_PROGRESS)
        )
    ).scalar_one()

    deals_by_stage = await get_deals_by_stage(db)

    return {
        "total_users": total_users,
        "total_clubs": total_clubs,
        "total_players": total_players,
        "active_sales": active_sales,
        "open_offers": open_offers,
        "active_deals": active_deals,
        "deals_by_stage": deals_by_stage,
    }


# ── Offers (admin) ────────────────────────────────────────────────────────────


async def admin_list_offers(
    db: AsyncSession,
    *,
    status: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    page: int = 1,
    page_size: int = 30,
):
    from app.offers.models import Offer, OfferMessage, OfferEvent, OfferStatus
    from sqlalchemy.orm import selectinload

    q = select(Offer).options(
        selectinload(Offer.player),
        selectinload(Offer.from_club),
        selectinload(Offer.to_club),
        selectinload(Offer.messages).selectinload(OfferMessage.sender_club),
        selectinload(Offer.events),
    )
    if status:
        q = q.where(Offer.status == OfferStatus(status))
    q = apply_date_range(q, Offer.last_action_at, date_from, date_to)

    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar_one()
    rows = await db.execute(
        q.order_by(Offer.last_action_at.desc()).offset((page - 1) * page_size).limit(page_size)
    )
    return list(rows.scalars()), total


# ── World import ──────────────────────────────────────────────────────────────


async def import_world_team_as_club(
    db: AsyncSession,
    *,
    world_team_id: uuid.UUID,
    user_id: uuid.UUID,
    role: str = "BOTH",
    transfer_budget=0,
    wage_budget=0,
):
    """Create a Club pre-filled from a WorldTeam and assign it to a user."""
    from app.clubs.models import Club, ClubFinance, ClubRole
    from app.world.models import WorldTeam
    from app.auth.models import User

    world_team = await db.get(WorldTeam, world_team_id)
    if world_team is None:
        raise ValueError("World team not found")

    user = await db.get(User, user_id)
    if user is None:
        raise ValueError("User not found")

    existing = await db.execute(
        select(Club).where(Club.user_id == user_id)
    )
    if existing.scalar_one_or_none() is not None:
        raise ValueError("This user already owns a club")

    club_role = ClubRole(role) if role in ClubRole.__members__ else ClubRole.BOTH
    club = Club(
        user_id=user_id,
        name=world_team.name,
        country=world_team.country,
        league_name=world_team.league_name,
        crest_url=world_team.crest_url,
        role=club_role,
    )
    db.add(club)
    await db.flush()

    finance = ClubFinance(
        club_id=club.id,
        transfer_budget_total=transfer_budget,
        wage_budget_total_weekly=wage_budget,
    )
    db.add(finance)
    await db.flush()
    return club


async def import_world_team_squad(
    db: AsyncSession,
    *,
    world_team_id: uuid.UUID,
    club_id: uuid.UUID,
) -> dict:
    """Assign all world-team players to a TransferX club as CONTRACTED.
    Creates a proper Contract record for each player so normalize_player_status
    works correctly. Players already assigned to another TransferX club are skipped."""
    from app.players.models import Player
    from app.players import service as players_service

    result = await db.execute(
        select(Player).where(Player.world_team_id == world_team_id)
    )
    players = list(result.scalars())

    imported = 0
    skipped = 0
    for player in players:
        if player.current_club_id is not None:
            skipped += 1
            continue
        # Create a real Contract record — this calls normalize_player_status
        # which sets current_club_id and status=CONTRACTED correctly
        await players_service.create_contract(db, player, club_id)
        imported += 1

    return {"imported": imported, "skipped": skipped}


async def get_deals_by_stage(db: AsyncSession) -> dict:
    """Return count of active deals grouped by stage."""
    from app.deals.models import Deal, DealStage, DealStatus

    rows = await db.execute(
        select(Deal.stage, func.count().label("cnt"))
        .where(Deal.status == DealStatus.IN_PROGRESS)
        .group_by(Deal.stage)
    )
    result = {stage.value: 0 for stage in (DealStage.AGREEMENT, DealStage.PAPERWORK, DealStage.CONFIRMED)}
    for stage, cnt in rows:
        result[stage.value] = cnt
    return result


async def get_activity_feed(db: AsyncSession, limit: int = 50) -> list[dict]:
    """Return a combined feed of recent system events (last 30 days)."""
    from app.auth.models import User
    from app.deals.models import Deal, DealStatus
    from app.sales.models import Sale, SaleStatus

    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    items: list[dict] = []

    # New users
    users = (await db.execute(
        select(User).where(User.created_at >= cutoff).order_by(User.created_at.desc()).limit(20)
    )).scalars()
    for u in users:
        items.append({
            "event_type": "USER_JOINED",
            "message": f"New user registered: {u.email}",
            "link": None,
            "entity_id": str(u.id),
            "occurred_at": u.created_at,
        })

    # New sales
    sales = (await db.execute(
        select(Sale)
        .options(selectinload(Sale.player), selectinload(Sale.seller_club))
        .where(Sale.created_at >= cutoff)
        .order_by(Sale.created_at.desc())
        .limit(20)
    )).scalars()
    for s in sales:
        player_name = s.player.name if s.player else "Unknown player"
        club_name = s.seller_club.name if s.seller_club else "Unknown club"
        items.append({
            "event_type": "SALE_CREATED",
            "message": f"{club_name} listed {player_name} for sale",
            "link": f"/market/sales/{s.id}",
            "entity_id": str(s.id),
            "occurred_at": s.created_at,
        })

    # Completed/collapsed deals
    deals = (await db.execute(
        select(Deal)
        .options(selectinload(Deal.player), selectinload(Deal.buyer_club), selectinload(Deal.seller_club))
        .where(
            Deal.status.in_([DealStatus.COMPLETED, DealStatus.COLLAPSED]),
            Deal.updated_at >= cutoff,
        )
        .order_by(Deal.updated_at.desc())
        .limit(20)
    )).scalars()
    for d in deals:
        player_name = d.player.name if d.player else "Unknown"
        buyer = d.buyer_club.name if d.buyer_club else "?"
        seller = d.seller_club.name if d.seller_club else "?"
        if d.status == DealStatus.COMPLETED:
            items.append({
                "event_type": "DEAL_COMPLETED",
                "message": f"Transfer completed: {player_name} ({seller} → {buyer})",
                "link": f"/deals/{d.id}",
                "entity_id": str(d.id),
                "occurred_at": d.updated_at,
            })
        else:
            items.append({
                "event_type": "DEAL_COLLAPSED",
                "message": f"Deal collapsed: {player_name} ({seller} → {buyer})",
                "link": f"/deals/{d.id}",
                "entity_id": str(d.id),
                "occurred_at": d.updated_at,
            })

    items.sort(key=lambda x: x["occurred_at"], reverse=True)
    return items[:limit]


async def broadcast_notification(db: AsyncSession, message: str, link: str | None = None) -> int:
    """Send a SYSTEM_BROADCAST to every active user, through the normal path:
    each person's preference is respected and their bell refreshes. Returns
    how many received it."""
    from app.auth.models import User
    from app.notifications.models import NotificationType
    from app.notifications.service import create_notification

    user_ids = list((await db.execute(select(User.id).where(User.is_active.is_(True)))).scalars())
    sent = 0
    for user_id in user_ids:
        if await create_notification(
            db, recipient_user_id=uuid.UUID(str(user_id)), type=NotificationType.SYSTEM_BROADCAST,
            message=message, link=link,
        ) is not None:
            sent += 1
    return sent


async def get_health_report(db: AsyncSession) -> dict:
    """Run data integrity checks and return a list of issues."""
    from datetime import datetime, timezone
    from app.deals.models import Deal, DealStage, DealStatus
    from app.players.models import Player, PlayerStatus
    from app.sales.models import Sale, SaleStatus
    from sqlalchemy.orm import selectinload

    now = datetime.now(timezone.utc)
    issues = []

    # 1. Deals stuck in AGREEMENT for >3 days
    stale_agreement_cutoff = now - timedelta(days=3)
    stale_agreement = (await db.execute(
        select(Deal)
        .options(selectinload(Deal.player), selectinload(Deal.buyer_club), selectinload(Deal.seller_club))
        .where(
            Deal.status == DealStatus.IN_PROGRESS,
            Deal.stage == DealStage.AGREEMENT,
            Deal.updated_at < stale_agreement_cutoff,
        )
    )).scalars().all()
    if stale_agreement:
        issues.append({
            "severity": "warning",
            "category": "deals",
            "message": f"{len(stale_agreement)} deal(s) stuck in Agreement for >3 days",
            "count": len(stale_agreement),
            "details": [
                {
                    "id": str(d.id),
                    "label": f"{d.player.name if d.player else '?'} — {d.buyer_club.name if d.buyer_club else '?'} vs {d.seller_club.name if d.seller_club else '?'}",
                }
                for d in stale_agreement
            ],
        })

    # 2. Deals stuck in PAPERWORK or CONFIRMED for >7 days
    stale_late_cutoff = now - timedelta(days=7)
    stale_late = (await db.execute(
        select(Deal)
        .options(selectinload(Deal.player), selectinload(Deal.buyer_club), selectinload(Deal.seller_club))
        .where(
            Deal.status == DealStatus.IN_PROGRESS,
            Deal.stage.in_([DealStage.PAPERWORK, DealStage.CONFIRMED]),
            Deal.updated_at < stale_late_cutoff,
        )
    )).scalars().all()
    if stale_late:
        issues.append({
            "severity": "critical",
            "category": "deals",
            "message": f"{len(stale_late)} deal(s) stuck in Paperwork/Confirmed for >7 days",
            "count": len(stale_late),
            "details": [
                {
                    "id": str(d.id),
                    "label": f"{d.player.name if d.player else '?'} — {d.stage.value} — {d.buyer_club.name if d.buyer_club else '?'} vs {d.seller_club.name if d.seller_club else '?'}",
                }
                for d in stale_late
            ],
        })

    # 3. Open sales with expired deadlines
    expired_sales = (await db.execute(
        select(Sale)
        .options(selectinload(Sale.player), selectinload(Sale.seller_club))
        .where(
            Sale.status == SaleStatus.OPEN,
            Sale.deadline != None,  # noqa: E711
            Sale.deadline < now,
        )
    )).scalars().all()
    if expired_sales:
        issues.append({
            "severity": "warning",
            "category": "sales",
            "message": f"{len(expired_sales)} sale(s) are OPEN but deadline has passed",
            "count": len(expired_sales),
            "details": [
                {
                    "id": str(s.id),
                    "label": f"{s.player.name if s.player else '?'} — {s.seller_club.name if s.seller_club else '?'}",
                }
                for s in expired_sales
            ],
        })

    # 4. Players marked CONTRACTED but have no active contract
    from app.players.models import Contract
    contracted_players = (await db.execute(
        select(Player)
        .options(selectinload(Player.contracts))
        .where(Player.status == PlayerStatus.CONTRACTED)
    )).scalars().all()
    orphaned = [
        p for p in contracted_players
        if not any(c.is_active for c in p.contracts)
    ]
    if orphaned:
        issues.append({
            "severity": "warning",
            "category": "contracts",
            "message": f"{len(orphaned)} player(s) marked CONTRACTED but have no active contract",
            "count": len(orphaned),
            "details": [
                {"id": str(p.id), "label": p.name}
                for p in orphaned[:20]
            ],
        })

    # 5. Players marked FREE_AGENT but have an active contract
    free_players = (await db.execute(
        select(Player)
        .options(selectinload(Player.contracts))
        .where(Player.status == PlayerStatus.FREE_AGENT)
    )).scalars().all()
    mismatched = [
        p for p in free_players
        if any(c.is_active for c in p.contracts)
    ]
    if mismatched:
        issues.append({
            "severity": "warning",
            "category": "contracts",
            "message": f"{len(mismatched)} player(s) marked FREE_AGENT but have an active contract",
            "count": len(mismatched),
            "details": [
                {"id": str(p.id), "label": p.name}
                for p in mismatched[:20]
            ],
        })

    return {
        "issues": issues,
        "checked_at": now,
        "healthy": len(issues) == 0,
    }


async def admin_force_withdraw_offer(db: AsyncSession, offer, *, reason: str) -> None:
    """Withdraw an open offer as TransferX staff: the buyer's reserved budget
    is released and both clubs are told why (offers.service)."""
    from app.offers.service import staff_withdraw_offer

    await staff_withdraw_offer(db, offer, reason=reason)


async def describe_users(db: AsyncSession, users) -> dict:
    """For each user: their club and role, agency, or player, in a few
    queries for the whole page. {user_id: {club_name, club_id, role, profile_label}}."""
    from app.auth.models import AgentProfile, PlayerProfile
    from app.clubs.models import Club, ClubStaff
    from app.players.models import Player

    ids = [u.id for u in users]
    out: dict = {uid: {} for uid in ids}
    if not ids:
        return out
    for club_id, name, owner in (await db.execute(select(Club.id, Club.name, Club.user_id).where(Club.user_id.in_(ids)))).all():
        out[owner].update(club_name=name, club_id=club_id, role="OWNER")
    for user_id, role, club_id, name in (await db.execute(
        select(ClubStaff.user_id, ClubStaff.role, Club.id, Club.name).join(Club, Club.id == ClubStaff.club_id)
        .where(ClubStaff.user_id.in_(ids))
    )).all():
        out[user_id].update(club_name=name, club_id=club_id, role=getattr(role, "value", role))
    for user_id, display, agency in (await db.execute(
        select(AgentProfile.user_id, AgentProfile.display_name, AgentProfile.agency_name).where(AgentProfile.user_id.in_(ids))
    )).all():
        out[user_id]["profile_label"] = " · ".join(x for x in (display, agency) if x)
    for user_id, name in (await db.execute(
        select(PlayerProfile.user_id, Player.name).join(Player, Player.id == PlayerProfile.player_id)
        .where(PlayerProfile.user_id.in_(ids))
    )).all():
        out[user_id]["profile_label"] = name
    return out


# ── Health: services and scheduled jobs ──────────────────────────────────────

_vendor_status_cache: dict = {}


async def _vendor_status() -> tuple[bool, str]:
    """API-Football's own count of today's requests (its /status endpoint,
    which doesn't count against the allowance). Cached for 5 minutes."""
    import time

    import httpx

    from app.config import settings

    if not settings.apisports_key:
        return False, "Not set up (APISPORTS_KEY): player data can't be refreshed"
    hit = _vendor_status_cache.get("v")
    if hit and hit[0] > time.monotonic():
        return hit[1]
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(f"{settings.api_football_base_url}/status",
                                    headers={"x-apisports-key": settings.apisports_key})
        data = resp.json().get("response") or {}
        req = data.get("requests") or {}
        used, limit = int(req.get("current") or 0), int(req.get("limit_day") or 0)
        result = (used < limit if limit else True,
                  f"{used:,} of {limit:,} requests used today" if limit else "Connected")
    except Exception as exc:  # network, bad key, plan problem
        result = (False, f"Couldn't reach API-Football: {str(exc)[:120]}")
    _vendor_status_cache["v"] = (time.monotonic() + 300, result)
    return result


async def get_services_and_jobs(db: AsyncSession) -> tuple[list[dict], list[dict]]:
    """What the platform depends on, and whether each is working; and every
    scheduled job with when it last ran and runs next."""
    from app.ai.assist import ai_available
    from app.common.jobs import JOB_LABELS, RUNS, every
    from app.config import settings
    from app.notifications.models import PushDelivery, PushDeliveryStatus, PushSubscription
    from app.notifications.push import vapid_configured

    services = [{"key": "database", "label": "Database", "ok": True, "detail": "Connected"}]
    services.append({
        "key": "email", "label": "Email", "ok": bool(settings.smtp_host),
        "detail": f"Sending through {settings.smtp_host}" if settings.smtp_host
        else "Not set up (SMTP_HOST): emails, digests and invitation emails are skipped",
    })
    if vapid_configured():
        devices = (await db.execute(select(func.count()).select_from(PushSubscription))).scalar_one()
        held = (await db.execute(select(func.count()).select_from(PushDelivery).where(
            PushDelivery.status == PushDeliveryStatus.HELD))).scalar_one()
        detail = f"{devices} device{'s' if devices != 1 else ''} subscribed" + (f", {held} held for quiet hours" if held else "")
        services.append({"key": "push", "label": "Phone notifications", "ok": True, "detail": detail})
    else:
        services.append({"key": "push", "label": "Phone notifications", "ok": False,
                         "detail": "Not set up (VAPID keys): nothing is pushed to phones"})
    services.append({
        "key": "ai", "label": "AI assistant", "ok": ai_available(),
        "detail": f"Model {settings.llm_model}" if ai_available() else "Not set up: assistant features are off",
    })
    ok, detail = await _vendor_status()
    services.append({"key": "vendor", "label": "API-Football", "ok": ok, "detail": detail})
    from app.common import slack as _slack
    from app.monitoring.models import JobRun

    services.append({
        "key": "slack", "label": "Slack", "ok": _slack.configured(),
        "detail": "Run messages and alerts go to the webhook's channel" if _slack.configured()
        else "Not set up (SLACK_WEBHOOK_URL): no run messages or alerts",
    })
    last_refresh = (await db.execute(select(JobRun).where(JobRun.job == "daily_refresh", JobRun.parent_id.is_(None),
                                                          JobRun.status.in_(["succeeded", "partial", "failed"]))
                                     .order_by(JobRun.started_at.desc()).limit(1))).scalar_one_or_none()
    remaining = ((last_refresh.summary or {}).get("api_remaining") if last_refresh else None)
    services.append({
        "key": "refresh", "label": "Data refresh (stats-worker)",
        "ok": bool(last_refresh and last_refresh.status != "failed"),
        "detail": (f"Last run {last_refresh.status}"
                   + (f", {remaining:,} API-Football requests left that day" if remaining is not None else ""))
        if last_refresh else "Hasn't run yet: set up the stats-worker service (see the spec)",
    })
    pool = getattr(db.bind, "pool", None)
    if pool is not None and hasattr(pool, "checkedout"):
        services[0]["detail"] = f"Connected · {pool.checkedout()} of {pool.size()} pooled connections in use"

    jobs = []
    from app.common.jobs import saved_runs

    saved = await saved_runs(db)  # what the last process knew, if it restarted since
    try:
        from app.main import _scheduler

        running = _scheduler.running
        for job in sorted(_scheduler.get_jobs(), key=lambda j: j.id):
            run = RUNS.get(job.id) or saved.get(job.id, {})
            jobs.append({
                "id": job.id, "label": JOB_LABELS.get(job.id, job.id.replace("_", " ").capitalize()),
                "every": every(job.trigger), "next_run_at": job.next_run_time,
                "last_run_at": run.get("last_run_at"), "last_ok": run.get("last_ok"), "last_error": run.get("last_error"),
            })
    except Exception:
        running = False
    services.append({"key": "scheduler", "label": "Scheduled jobs", "ok": running,
                     "detail": f"Running {len(jobs)} jobs" if running else "Not running: reminders, expiries and digests are stopped"})
    return services, jobs
