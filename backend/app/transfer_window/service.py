"""Transfer window service — window lookup and enforcement check."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.transfer_window.models import TransferWindow


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _window_is_open(w: TransferWindow) -> bool:
    now = _now()
    opens = w.opens_at if w.opens_at.tzinfo else w.opens_at.replace(tzinfo=timezone.utc)
    closes = w.closes_at if w.closes_at.tzinfo else w.closes_at.replace(tzinfo=timezone.utc)
    return opens <= now <= closes


def _association_filter(association: str | None):
    """SQLAlchemy filter: windows with no association (global) or matching the given one."""
    if association:
        return or_(TransferWindow.association.is_(None), TransferWindow.association == association)
    return TransferWindow.association.is_(None)


async def get_current_window(db: AsyncSession, *, association: str | None = None) -> TransferWindow | None:
    now = _now()
    result = await db.execute(
        select(TransferWindow)
        .where(
            TransferWindow.opens_at <= now,
            TransferWindow.closes_at >= now,
            _association_filter(association),
        )
        .order_by(TransferWindow.opens_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_next_window(db: AsyncSession, *, association: str | None = None) -> TransferWindow | None:
    now = _now()
    result = await db.execute(
        select(TransferWindow)
        .where(TransferWindow.opens_at > now, _association_filter(association))
        .order_by(TransferWindow.opens_at.asc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def has_applicable_windows(db: AsyncSession, *, association: str | None = None) -> bool:
    """True if any window applies to this association (global windows always count)."""
    result = await db.execute(
        select(func.count()).select_from(TransferWindow).where(_association_filter(association))
    )
    return (result.scalar_one() or 0) > 0


async def is_transfer_allowed(db: AsyncSession, *, association: str | None = None) -> bool:
    """Returns True if a transfer may happen right now for the given association.

    association=None matches only global windows (no association set).
    association="England" matches global windows plus England-specific ones.

    If no windows that apply to this association exist at all, the result depends
    on settings.transferx_windows_fail_closed: False (default, dev-safe) treats an
    unconfigured calendar as an open market; True (recommended for production)
    fails closed instead, so a forgotten window calendar can't silently allow
    every transfer.
    """
    applicable_count_result = await db.execute(
        select(func.count()).select_from(TransferWindow).where(_association_filter(association))
    )
    if (applicable_count_result.scalar_one() or 0) == 0:
        return not settings.transferx_windows_fail_closed
    return await get_current_window(db, association=association) is not None


async def can_complete_deal(
    db: AsyncSession, *, association: str | None, confirmed_at: datetime | None
) -> bool:
    """Deadline-day 'deal sheet' grace for completing an already-confirmed deal.

    If the window is currently open (or none applies), completion is always
    allowed. Otherwise, a deal that was confirmed (PAPERWORK → CONFIRMED) while
    a matching window was still open may still complete for that window's
    grace_period_hours after it closed — mirroring the real-world practice of
    filing a deal sheet before the deadline and finishing paperwork shortly after.
    """
    if await is_transfer_allowed(db, association=association):
        return True
    if confirmed_at is None:
        return False

    confirmed = confirmed_at if confirmed_at.tzinfo else confirmed_at.replace(tzinfo=timezone.utc)
    now = _now()
    result = await db.execute(
        select(TransferWindow).where(_association_filter(association))
    )
    for w in result.scalars():
        opens = w.opens_at if w.opens_at.tzinfo else w.opens_at.replace(tzinfo=timezone.utc)
        closes = w.closes_at if w.closes_at.tzinfo else w.closes_at.replace(tzinfo=timezone.utc)
        grace_end = closes + timedelta(hours=w.grace_period_hours or 0)
        if opens <= confirmed <= closes and now <= grace_end:
            return True
    return False


async def list_windows(db: AsyncSession) -> list[TransferWindow]:
    result = await db.execute(select(TransferWindow).order_by(TransferWindow.opens_at.desc()))
    return list(result.scalars())


async def create_window(
    db: AsyncSession,
    name: str,
    opens_at: datetime,
    closes_at: datetime,
    association: str | None = None,
    grace_period_hours: int = 24,
) -> TransferWindow:
    w = TransferWindow(
        name=name, opens_at=opens_at, closes_at=closes_at,
        association=association, grace_period_hours=grace_period_hours,
    )
    db.add(w)
    await db.flush()
    return w


async def get_window_by_id(db: AsyncSession, window_id) -> TransferWindow | None:
    result = await db.execute(select(TransferWindow).where(TransferWindow.id == window_id))
    return result.scalar_one_or_none()


async def update_window(db: AsyncSession, window_id, updates: dict) -> TransferWindow | None:
    """Admin override of an existing window's name/association/dates/grace period."""
    w = await get_window_by_id(db, window_id)
    if w is None:
        return None

    for k, v in updates.items():
        setattr(w, k, v)

    opens = w.opens_at if w.opens_at.tzinfo else w.opens_at.replace(tzinfo=timezone.utc)
    closes = w.closes_at if w.closes_at.tzinfo else w.closes_at.replace(tzinfo=timezone.utc)
    if closes <= opens:
        raise ValueError("closes_at must be after opens_at")

    await db.flush()
    return w


async def delete_window(db: AsyncSession, window_id, *, reason: str, actor_user_id=None) -> bool:
    from app.audit import service as audit_service

    if not reason or not reason.strip():
        raise ValueError("A reason is required to delete a transfer window — it lands in the audit trail.")

    result = await db.execute(select(TransferWindow).where(TransferWindow.id == window_id))
    w = result.scalar_one_or_none()
    if w is None:
        return False

    reason = reason.strip()
    await audit_service.emit(
        db,
        entity_type="TRANSFER_WINDOW", entity_id=w.id,
        action="TRANSFER_WINDOW_DELETED",
        actor_user_id=actor_user_id,
        payload={"reason": reason, "name": w.name, "association": w.association},
        description=f"Transfer window '{w.name}' deleted by staff. Reason: {reason}",
    )
    await db.delete(w)
    await db.flush()
    return True
