"""Transfer window service — window lookup and enforcement check."""
from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.transfer_window.models import TransferWindow


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _window_is_open(w: TransferWindow) -> bool:
    now = _now()
    opens = w.opens_at if w.opens_at.tzinfo else w.opens_at.replace(tzinfo=timezone.utc)
    closes = w.closes_at if w.closes_at.tzinfo else w.closes_at.replace(tzinfo=timezone.utc)
    return opens <= now <= closes


async def get_current_window(db: AsyncSession) -> TransferWindow | None:
    now = _now()
    result = await db.execute(
        select(TransferWindow)
        .where(TransferWindow.opens_at <= now, TransferWindow.closes_at >= now)
        .order_by(TransferWindow.opens_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_next_window(db: AsyncSession) -> TransferWindow | None:
    now = _now()
    result = await db.execute(
        select(TransferWindow)
        .where(TransferWindow.opens_at > now)
        .order_by(TransferWindow.opens_at.asc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def any_window_exists(db: AsyncSession) -> bool:
    result = await db.execute(select(func.count()).select_from(TransferWindow))
    return (result.scalar_one() or 0) > 0


async def is_transfer_allowed(db: AsyncSession) -> bool:
    """Returns True if a transfer/offer/sale may be created right now."""
    if not await any_window_exists(db):
        return True  # No windows configured — open market
    return await get_current_window(db) is not None


async def list_windows(db: AsyncSession) -> list[TransferWindow]:
    result = await db.execute(select(TransferWindow).order_by(TransferWindow.opens_at.desc()))
    return list(result.scalars())


async def create_window(db: AsyncSession, name: str, opens_at: datetime, closes_at: datetime) -> TransferWindow:
    w = TransferWindow(name=name, opens_at=opens_at, closes_at=closes_at)
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
