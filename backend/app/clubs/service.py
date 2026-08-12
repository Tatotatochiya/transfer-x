import hashlib
import hmac
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.clubs.models import (
    Club,
    ClubFinance,
    ClubRole,
    ClubStaff,
    ClubStaffInvitation,
    PlayerSearchView,
    StaffRole,
)
from app.clubs.schemas import CommitmentItem


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


async def get_club_membership_role(db: AsyncSession, user_id: uuid.UUID) -> str | None:
    """Lean role-only resolution: 'OWNER' | StaffRole value | None (no membership).

    The capability check runs on every gated request — this avoids loading the
    club row (and its finance) when only the role is needed. Max two indexed
    single-row lookups; one for owners.
    """
    result = await db.execute(select(Club.id).where(Club.user_id == user_id))
    if result.first() is not None:
        return "OWNER"
    staff = await get_staff_by_user_id(db, user_id)
    return staff.role.value if staff else None


async def list_club_staff(db: AsyncSession, club_id: uuid.UUID) -> list[ClubStaff]:
    result = await db.execute(
        select(ClubStaff)
        .where(ClubStaff.club_id == club_id)
        .options(selectinload(ClubStaff.user))
        .order_by(ClubStaff.created_at)
    )
    return list(result.scalars())


async def get_staff_with_user(
    db: AsyncSession, staff_id: uuid.UUID, club_id: uuid.UUID
) -> ClubStaff | None:
    """A staff row scoped to a club (owner-facing team management), user loaded."""
    result = await db.execute(
        select(ClubStaff)
        .where(
            ClubStaff.id == uuid.UUID(str(staff_id)),
            ClubStaff.club_id == uuid.UUID(str(club_id)),
        )
        .options(selectinload(ClubStaff.user))
    )
    return result.scalar_one_or_none()


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


# ── Staff invitations (TRA-86, D6) ────────────────────────────────────────────

INVITATION_TTL_DAYS = 7


def _hash_invitation_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode()).hexdigest()


def invitation_is_live(inv: ClubStaffInvitation) -> bool:
    """Live = not accepted, not revoked, not expired."""
    if inv.accepted_at is not None or inv.revoked_at is not None:
        return False
    expires = inv.expires_at
    if expires.tzinfo is None:  # SQLite drops tzinfo
        expires = expires.replace(tzinfo=timezone.utc)
    return expires > datetime.now(timezone.utc)


async def create_staff_invitation(
    db: AsyncSession,
    *,
    club_id: uuid.UUID,
    email: str,
    role: StaffRole,
    invited_by_user_id: uuid.UUID,
) -> tuple[ClubStaffInvitation, str]:
    """Create an invitation; returns (row, raw_token). The raw token appears in
    exactly one API response and is never stored or logged (gotcha #7).

    Raises ValueError for: an email that already belongs to any User
    (account-linking is out of scope), or a still-live invitation for the same
    email at this club. Both comparisons are case-insensitive.
    """
    from app.auth.models import User

    email_norm = email.strip().lower()

    existing_user = await db.execute(select(User.id).where(func.lower(User.email) == email_norm))
    if existing_user.first() is not None:
        raise ValueError(
            "This email already has a TransferX account. Linking existing accounts "
            "to a club is not supported — the user must join with a new email."
        )

    pending = await db.execute(
        select(ClubStaffInvitation).where(
            ClubStaffInvitation.club_id == uuid.UUID(str(club_id)),
            func.lower(ClubStaffInvitation.email) == email_norm,
            ClubStaffInvitation.accepted_at.is_(None),
            ClubStaffInvitation.revoked_at.is_(None),
        )
    )
    for inv in pending.scalars():
        if invitation_is_live(inv):
            raise ValueError("A pending invitation for this email already exists — revoke it first.")

    raw_token = secrets.token_urlsafe(32)
    invitation = ClubStaffInvitation(
        club_id=uuid.UUID(str(club_id)),
        email=email_norm,
        role=role,
        token_hash=_hash_invitation_token(raw_token),
        invited_by_user_id=invited_by_user_id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=INVITATION_TTL_DAYS),
    )
    db.add(invitation)
    await db.flush()
    return invitation, raw_token


async def get_live_invitation_by_token(
    db: AsyncSession, raw_token: str
) -> ClubStaffInvitation | None:
    """Resolve a raw token to a live invitation, or None — with no oracle on
    which failure (unknown/expired/revoked/accepted all look identical)."""
    digest = _hash_invitation_token(raw_token)
    result = await db.execute(
        select(ClubStaffInvitation).where(ClubStaffInvitation.token_hash == digest)
    )
    inv = result.scalar_one_or_none()
    if inv is None:
        return None
    # Belt-and-braces constant-time comparison on top of the indexed lookup.
    if not hmac.compare_digest(inv.token_hash, digest):
        return None
    return inv if invitation_is_live(inv) else None


async def list_pending_invitations(db: AsyncSession, club_id: uuid.UUID) -> list[ClubStaffInvitation]:
    result = await db.execute(
        select(ClubStaffInvitation)
        .where(
            ClubStaffInvitation.club_id == uuid.UUID(str(club_id)),
            ClubStaffInvitation.accepted_at.is_(None),
            ClubStaffInvitation.revoked_at.is_(None),
        )
        .order_by(ClubStaffInvitation.created_at)
    )
    return [inv for inv in result.scalars() if invitation_is_live(inv)]


async def get_invitation_by_id(
    db: AsyncSession, invitation_id: uuid.UUID, club_id: uuid.UUID
) -> ClubStaffInvitation | None:
    result = await db.execute(
        select(ClubStaffInvitation).where(
            ClubStaffInvitation.id == uuid.UUID(str(invitation_id)),
            ClubStaffInvitation.club_id == uuid.UUID(str(club_id)),
        )
    )
    return result.scalar_one_or_none()


async def revoke_invitation(db: AsyncSession, invitation: ClubStaffInvitation) -> None:
    invitation.revoked_at = datetime.now(timezone.utc)
    await db.flush()


async def accept_staff_invitation(
    db: AsyncSession, invitation: ClubStaffInvitation, password: str
) -> tuple["User", ClubStaff]:  # type: ignore[name-defined]
    """Create the staff User (explicit user_type=CLUB — D9) + ClubStaff row and
    stamp the invitation accepted. Caller must have verified the token is live."""
    from app.auth import service as auth_service
    from app.auth.models import User, UserType

    existing = await db.execute(
        select(User.id).where(func.lower(User.email) == invitation.email.lower())
    )
    if existing.first() is not None:
        raise ValueError("This email already has a TransferX account.")

    user = User(
        email=invitation.email,
        hashed_password=auth_service.hash_password(password),
        is_active=True,
        is_superuser=False,
        user_type=UserType.CLUB,
    )
    db.add(user)
    await db.flush()

    staff = await create_club_staff(
        db,
        club_id=uuid.UUID(str(invitation.club_id)),
        user_id=user.id,
        role=invitation.role,
        created_by_user_id=invitation.invited_by_user_id,
    )
    invitation.accepted_at = datetime.now(timezone.utc)
    await db.flush()
    return user, staff


async def remove_club_staff(db: AsyncSession, staff: ClubStaff) -> None:
    """D10: staff removal deletes the membership row and deactivates the user —
    a staff account has no purpose outside its club, and is_active is checked
    on every authenticated request, so access dies immediately."""
    from app.auth.models import User

    user = await db.get(User, staff.user_id)
    await db.delete(staff)
    if user is not None:
        user.is_active = False
    await db.flush()


def can_sell(role: ClubRole) -> bool:
    return role in (ClubRole.SELLER, ClubRole.BOTH, ClubRole.ADMIN)


def can_buy(role: ClubRole) -> bool:
    return role in (ClubRole.BUYER, ClubRole.BOTH, ClubRole.ADMIN)


async def get_finance_for_update(db: AsyncSession, club_id: uuid.UUID) -> ClubFinance | None:
    """Fetch ClubFinance row with a row-level lock (SELECT FOR UPDATE).

    populate_existing forces the locked row to refresh the identity-map instance —
    without it, a finance row already loaded earlier in the session (e.g. via
    selectinload(Club.finance)) would be returned with stale attribute values,
    defeating the lock under concurrent read-modify-write.
    """
    result = await db.execute(
        select(ClubFinance)
        .where(ClubFinance.club_id == club_id)
        .with_for_update()
        .execution_options(populate_existing=True)
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


async def get_commitments(db: AsyncSession, club_id: uuid.UUID) -> list[CommitmentItem]:
    """B5: row-level attribution of this club's transfer_reserved/committed and
    wage_reserved_weekly/committed_weekly ClubFinance totals — replacing
    FinancePage.tsx's CommitmentsTable client reconstruction, which its own
    code comment admits misses sale bids and all wage commitments and isn't
    guaranteed to sum to the real totals.

    Walks every real source of reserve_budget/commit_budget (not a parallel
    query path): offers this club sent (still SENT/COUNTERED → reserved),
    active bids this club placed (→ reserved), and deals in progress with
    this club as buyer (→ committed, net of any instalments already paid).
    Local imports avoid a circular import — offers/deals/sales all import
    `clubs` at module level already.
    """
    from sqlalchemy.orm import selectinload

    from app.deals import service as deals_service
    from app.deals.models import DealStatus
    from app.offers import service as offers_service
    from app.offers.models import OfferStatus
    from app.sales.models import Bid, BidStatus, Sale

    items: list[CommitmentItem] = []

    offers, _ = await offers_service.list_offers(
        db, club_id=club_id, direction="sent", page=1, page_size=200
    )
    for o in offers:
        if o.status not in (OfferStatus.SENT, OfferStatus.COUNTERED):
            continue
        items.append(CommitmentItem(
            kind="offer",
            id=o.id,
            player_name=o.player.name if o.player else None,
            transfer_amount=o.fee_amount or Decimal("0"),
            wage_weekly_amount=o.wage_weekly,
            status="reserved",
            releases_when="Offer withdrawn, rejected, or resolved",
            link=f"/offers/{o.id}",
        ))

    bid_result = await db.execute(
        select(Bid)
        .where(Bid.buyer_club_id == club_id, Bid.status == BidStatus.ACTIVE)
        .options(selectinload(Bid.sale).selectinload(Sale.player))
    )
    for b in bid_result.scalars():
        items.append(CommitmentItem(
            kind="bid",
            id=b.id,
            player_name=b.sale.player.name if b.sale and b.sale.player else None,
            transfer_amount=b.reserved_transfer_amount,
            wage_weekly_amount=b.reserved_wage_weekly or None,
            status="reserved",
            releases_when="Outbid, sale closes, or bid withdrawn",
            link=f"/sales/{b.sale_id}",
        ))

    deals, _ = await deals_service.list_deals(db, club_id=club_id, page=1, page_size=200)
    for d in deals:
        if d.status not in (DealStatus.IN_PROGRESS, DealStatus.PENDING_COMPLETION):
            continue
        if d.buyer_club_id != club_id:
            continue  # committed budget is a buyer-side concept
        paid = sum((i.amount for i in (d.instalments or []) if i.paid), Decimal("0"))
        items.append(CommitmentItem(
            kind="deal",
            id=d.id,
            player_name=d.player.name if d.player else None,
            transfer_amount=max(Decimal("0"), d.agreed_fee - paid),
            wage_weekly_amount=d.agreed_wage_weekly,
            status="committed",
            releases_when="Deal completes or collapses",
            link=f"/deals/{d.id}",
        ))

    return items
