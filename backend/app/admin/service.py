"""M7 — Admin service layer."""

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select
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
        q = q.where(User.email.ilike(f"%{search}%"))
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

    if transfer_budget_total is not None:
        finance.transfer_budget_total = transfer_budget_total
    if wage_budget_total_weekly is not None:
        finance.wage_budget_total_weekly = wage_budget_total_weekly
    await db.flush()
    return finance


# ── User management (extended) ────────────────────────────────────────────────


async def create_user(db: AsyncSession, email: str, password: str):
    from app.auth.models import User
    from app.auth import service as auth_service

    existing = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if existing is not None:
        raise ValueError(f"Email {email} is already registered")

    user = User(
        email=email,
        hashed_password=auth_service.hash_password(password),
        is_active=True,
        is_superuser=False,
    )
    db.add(user)
    await db.flush()
    return user


async def reset_password(db: AsyncSession, user, new_password: str):
    from app.auth import service as auth_service

    user.hashed_password = auth_service.hash_password(new_password)
    await db.flush()
    return user


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


async def admin_cancel_sale(db: AsyncSession, sale):
    from app.sales.models import SaleStatus

    if sale.status not in (SaleStatus.OPEN,):
        raise ValueError(f"Sale is already {sale.status.value} — cannot cancel")
    sale.status = SaleStatus.CANCELLED
    await db.flush()
    return sale


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


async def create_staff_user(
    db: AsyncSession,
    club_id: uuid.UUID,
    email: str,
    password: str,
    role: str,
    created_by_user_id: uuid.UUID,
):
    """Create a new User + ClubStaff record."""
    from app.auth.models import User
    from app.clubs.models import ClubStaff, StaffRole
    from app.auth import service as auth_service

    # Check email not already taken
    existing = await db.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none() is not None:
        raise ValueError(f"Email {email} is already registered")

    staff_role = StaffRole(role)

    hashed = auth_service.hash_password(password)
    user = User(email=email, hashed_password=hashed, is_active=True, is_superuser=False)
    db.add(user)
    await db.flush()

    staff = ClubStaff(
        club_id=uuid.UUID(str(club_id)),
        user_id=user.id,
        role=staff_role,
        created_by_user_id=created_by_user_id,
    )
    db.add(staff)
    await db.flush()
    return staff, user


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
    """Send a SYSTEM_BROADCAST notification to all active users. Returns recipient count."""
    from app.auth.models import User
    from app.notifications.models import Notification, NotificationType

    users = (await db.execute(
        select(User).where(User.is_active == True)  # noqa: E712
    )).scalars()
    users = list(users)

    for user in users:
        db.add(Notification(
            recipient_user_id=uuid.UUID(str(user.id)),
            type=NotificationType.SYSTEM_BROADCAST,
            message=message,
            link=link,
        ))
    await db.flush()
    return len(users)


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


async def admin_force_withdraw_offer(db: AsyncSession, offer) -> None:
    from app.offers.models import OfferEvent, OfferEventType, OfferStatus

    _terminal = {OfferStatus.ACCEPTED, OfferStatus.REJECTED, OfferStatus.WITHDRAWN, OfferStatus.EXPIRED}
    if offer.status in _terminal:
        raise ValueError(f"Offer is already in terminal state: {offer.status.value}")

    offer.status = OfferStatus.WITHDRAWN
    db.add(OfferEvent(
        offer_id=offer.id,
        event_type=OfferEventType.WITHDRAWN,
        actor_club_id=None,
        payload={"admin_action": True},
    ))
    await db.flush()
