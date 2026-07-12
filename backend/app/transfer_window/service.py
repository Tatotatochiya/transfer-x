"""Transfer window service — window lookup and enforcement check."""
from datetime import datetime, timezone

from sqlalchemy import or_, select, func
from sqlalchemy.ext.asyncio import AsyncSession

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


async def any_window_exists(db: AsyncSession) -> bool:
    result = await db.execute(select(func.count()).select_from(TransferWindow))
    return (result.scalar_one() or 0) > 0


async def is_transfer_allowed(db: AsyncSession, *, association: str | None = None) -> bool:
    """Returns True if a transfer may happen right now for the given association.

    association=None matches only global windows (no association set).
    association="England" matches global windows plus England-specific ones.

    If no windows that apply to this association exist at all, returns True —
    the club is not subject to any window regime, so the market is open for them.
    (This is the correct real-world behaviour: an association-specific window
    calendar only regulates clubs in that association.)

    NOTE: the "no applicable windows → open" fallback is also a safe development
    default. Production deployments must configure windows to enforce the calendar.
    """
    applicable_count_result = await db.execute(
        select(func.count()).select_from(TransferWindow).where(_association_filter(association))
    )
    if (applicable_count_result.scalar_one() or 0) == 0:
        return True  # No applicable windows — open market
    return await get_current_window(db, association=association) is not None


async def list_windows(db: AsyncSession) -> list[TransferWindow]:
    result = await db.execute(select(TransferWindow).order_by(TransferWindow.opens_at.desc()))
    return list(result.scalars())


async def create_window(
    db: AsyncSession,
    name: str,
    opens_at: datetime,
    closes_at: datetime,
    association: str | None = None,
) -> TransferWindow:
    w = TransferWindow(name=name, opens_at=opens_at, closes_at=closes_at, association=association)
    db.add(w)
    await db.flush()
    return w


async def delete_window(db: AsyncSession, window_id) -> bool:
    result = await db.execute(select(TransferWindow).where(TransferWindow.id == window_id))
    w = result.scalar_one_or_none()
    if w is None:
        return False
    await db.delete(w)
    await db.flush()
    return True
