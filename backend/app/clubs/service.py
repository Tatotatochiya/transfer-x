import uuid
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.clubs.models import Club, ClubFinance, ClubRole, ClubStaff, PlayerSearchView, StaffRole


async def create_club(
    db: AsyncSession,
    user_id: uuid.UUID,
    name: str,
    role: ClubRole = ClubRole.BOTH,
) -> Club:
    club = Club(user_id=user_id, name=name, role=role)
    db.add(club)
    await db.flush()
    return club


async def create_club_finance(db: AsyncSession, club_id: uuid.UUID) -> ClubFinance:
    finance = ClubFinance(club_id=club_id)
    db.add(finance)
    await db.flush()
    return finance


async def get_club_by_user_id(db: AsyncSession, user_id: uuid.UUID) -> Club | None:
    result = await db.execute(
        select(Club)
        .where(Club.user_id == user_id)
        .options(selectinload(Club.finance))
    )
    return result.scalar_one_or_none()


async def get_club_by_id(db: AsyncSession, club_id: uuid.UUID) -> Club | None:
    result = await db.execute(
        select(Club)
        .where(Club.id == club_id)
        .options(selectinload(Club.finance))
    )
    return result.scalar_one_or_none()


async def update_club(db: AsyncSession, club: Club, **fields) -> Club:
    for key, value in fields.items():
        if value is not None:
            setattr(club, key, value)
    await db.flush()
    return club


async def list_clubs(
    db: AsyncSession,
    search: str | None,
    page: int,
    page_size: int,
    country: str | None = None,
    league_name: str | None = None,
    sort_by: str = "name",
    sort_dir: str = "asc",
) -> tuple[list[Club], int]:
    q = select(Club)
    if search:
        q = q.where(Club.name.ilike(f"%{search}%"))
    if country:
        q = q.where(Club.country.ilike(f"%{country}%"))
    if league_name:
        q = q.where(Club.league_name.ilike(f"%{league_name}%"))

    sort_col = {
        "name": Club.name,
        "country": Club.country,
        "league_name": Club.league_name,
        "created_at": Club.created_at,
    }.get(sort_by, Club.name)
    order_expr = sort_col.desc() if sort_dir == "desc" else sort_col.asc()

    total_result = await db.execute(select(func.count()).select_from(q.subquery()))
    total = total_result.scalar_one()

    rows = await db.execute(q.order_by(order_expr).offset((page - 1) * page_size).limit(page_size))
    return list(rows.scalars()), total


# ── Staff helpers ─────────────────────────────────────────────────────────────


async def get_staff_by_user_id(db: AsyncSession, user_id: uuid.UUID) -> ClubStaff | None:
    result = await db.execute(select(ClubStaff).where(ClubStaff.user_id == user_id))
    return result.scalar_one_or_none()


async def get_club_for_user(db: AsyncSession, user_id: uuid.UUID) -> Club | None:
    """Return the club for either an owner or a staff member."""
    club = await get_club_by_user_id(db, user_id)
    if club:
        return club
    staff = await get_staff_by_user_id(db, user_id)
    if staff:
        return await get_club_by_id(db, staff.club_id)
    return None


async def get_club_and_role_for_user(
    db: AsyncSession, user_id: uuid.UUID
) -> tuple["Club | None", str]:
    """Return (club, role) where role is 'OWNER', 'MANAGER', or 'READONLY'."""
    club = await get_club_by_user_id(db, user_id)
    if club:
        return club, "OWNER"
    staff = await get_staff_by_user_id(db, user_id)
    if staff:
        club = await get_club_by_id(db, staff.club_id)
        return club, staff.role.value
    return None, "OWNER"


async def list_club_staff(db: AsyncSession, club_id: uuid.UUID) -> list[ClubStaff]:
    result = await db.execute(
        select(ClubStaff).where(ClubStaff.club_id == club_id).order_by(ClubStaff.created_at)
    )
    return list(result.scalars())


async def create_club_staff(
    db: AsyncSession,
    club_id: uuid.UUID,
    user_id: uuid.UUID,
    role: StaffRole,
    created_by_user_id: uuid.UUID | None = None,
) -> ClubStaff:
    staff = ClubStaff(
        club_id=club_id,
        user_id=user_id,
        role=role,
        created_by_user_id=created_by_user_id,
    )
    db.add(staff)
    await db.flush()
    return staff


async def update_club_staff_role(db: AsyncSession, staff: ClubStaff, role: StaffRole) -> ClubStaff:
    staff.role = role
    await db.flush()
    return staff


async def delete_club_staff(db: AsyncSession, staff: ClubStaff) -> None:
    await db.delete(staff)
    await db.flush()


def can_sell(role: ClubRole) -> bool:
    return role in (ClubRole.SELLER, ClubRole.BOTH, ClubRole.ADMIN)


def can_buy(role: ClubRole) -> bool:
    return role in (ClubRole.BUYER, ClubRole.BOTH, ClubRole.ADMIN)


async def get_finance_for_update(db: AsyncSession, club_id: uuid.UUID) -> ClubFinance | None:
    """Fetch ClubFinance row with a row-level lock (SELECT FOR UPDATE)."""
    result = await db.execute(
        select(ClubFinance)
        .where(ClubFinance.club_id == club_id)
        .with_for_update()
    )
    return result.scalar_one_or_none()


async def reserve_budget(
    db: AsyncSession,
    club_id: uuid.UUID,
    transfer_amount: Decimal,
    wage_weekly: Decimal = Decimal("0"),
) -> ClubFinance:
    """Move funds from available → reserved (pending bid/offer).

    Raises ValueError if insufficient budget.
    """
    finance = await get_finance_for_update(db, club_id)
    if finance is None:
        raise ValueError("Club finance record not found")
    if finance.transfer_remaining < transfer_amount:
        raise ValueError(
            f"Insufficient transfer budget: need {transfer_amount}, "
            f"available {finance.transfer_remaining}"
        )
    if finance.wage_remaining_weekly < wage_weekly:
        raise ValueError(
            f"Insufficient wage budget: need {wage_weekly}, "
            f"available {finance.wage_remaining_weekly}"
        )
    finance.transfer_reserved += transfer_amount
    finance.wage_reserved_weekly += wage_weekly
    await db.flush()
    return finance


async def release_budget(
    db: AsyncSession,
    club_id: uuid.UUID,
    transfer_amount: Decimal,
    wage_weekly: Decimal = Decimal("0"),
) -> ClubFinance:
    """Release previously reserved funds back to available (bid withdrawn/outbid)."""
    finance = await get_finance_for_update(db, club_id)
    if finance is None:
        raise ValueError("Club finance record not found")
    finance.transfer_reserved = max(Decimal("0"), finance.transfer_reserved - transfer_amount)
    finance.wage_reserved_weekly = max(Decimal("0"), finance.wage_reserved_weekly - wage_weekly)
    await db.flush()
    return finance


# ── Player search views ───────────────────────────────────────────────────────


async def list_search_views(db: AsyncSession, club_id: uuid.UUID) -> list[PlayerSearchView]:
    result = await db.execute(
        select(PlayerSearchView)
        .where(PlayerSearchView.club_id == club_id)
        .order_by(PlayerSearchView.created_at)
    )
    return list(result.scalars())


async def get_search_view(db: AsyncSession, view_id: uuid.UUID, club_id: uuid.UUID) -> PlayerSearchView | None:
    result = await db.execute(
        select(PlayerSearchView).where(
            PlayerSearchView.id == view_id,
            PlayerSearchView.club_id == club_id,
        )
    )
    return result.scalar_one_or_none()


async def create_search_view(
    db: AsyncSession,
    club_id: uuid.UUID,
    name: str,
    filters: dict,
    is_default: bool = False,
) -> PlayerSearchView:
    if is_default:
        await _clear_default(db, club_id)
    view = PlayerSearchView(club_id=club_id, name=name, filters=filters, is_default=is_default)
    db.add(view)
    await db.flush()
    return view


async def update_search_view(
    db: AsyncSession,
    view: PlayerSearchView,
    *,
    name: str | None = None,
    filters: dict | None = None,
    is_default: bool | None = None,
) -> PlayerSearchView:
    if is_default is True:
        await _clear_default(db, view.club_id, exclude_id=view.id)
        view.is_default = True
    elif is_default is False:
        view.is_default = False
    if name is not None:
        view.name = name
    if filters is not None:
        view.filters = filters
    await db.flush()
    return view


async def delete_search_view(db: AsyncSession, view: PlayerSearchView) -> None:
    await db.delete(view)
    await db.flush()


async def _clear_default(
    db: AsyncSession, club_id: uuid.UUID, exclude_id: uuid.UUID | None = None
) -> None:
    """Remove is_default from all views for this club (optionally excluding one)."""
    from sqlalchemy import update as sa_update
    q = (
        sa_update(PlayerSearchView)
        .where(PlayerSearchView.club_id == club_id, PlayerSearchView.is_default == True)  # noqa: E712
        .values(is_default=False)
    )
    if exclude_id:
        q = q.where(PlayerSearchView.id != exclude_id)
    await db.execute(q)


async def commit_budget(
    db: AsyncSession,
    club_id: uuid.UUID,
    transfer_amount: Decimal,
    wage_weekly: Decimal = Decimal("0"),
) -> ClubFinance:
    """Move funds from reserved → committed (deal accepted/completed)."""
    finance = await get_finance_for_update(db, club_id)
    if finance is None:
        raise ValueError("Club finance record not found")
    finance.transfer_reserved = max(Decimal("0"), finance.transfer_reserved - transfer_amount)
    finance.wage_reserved_weekly = max(Decimal("0"), finance.wage_reserved_weekly - wage_weekly)
    finance.transfer_committed += transfer_amount
    finance.wage_committed_weekly += wage_weekly
    await db.flush()
    return finance
