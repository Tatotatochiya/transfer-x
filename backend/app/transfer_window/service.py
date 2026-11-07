"""Transfer window service: which windows govern a club, and what they hold.

A window is a registration period. Clubs talk, bid and agree deals all year;
what waits for a window is registering the player at his new club, so a
transfer between two clubs completes only while the buying club's window is
open (completion_hold). Free agents and pre-contracts don't wait: an
out-of-contract player can be registered at any time.

Each country sets its own windows (FIFA's registration period calendar), so a
window names one. A club follows its own country's windows, or, when its
country has none, the windows with no country. With no windows at all the
market is open.
"""
import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.transfer_window.models import TransferWindow

# How far ahead admins should have windows set up (coverage).
COVERAGE_DAYS = 183


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _key(country: str | None) -> str:
    return (country or "").strip().casefold()


def _window_is_open(w: TransferWindow, now: datetime | None = None) -> bool:
    now = now or _now()
    return _utc(w.opens_at) <= now <= _utc(w.closes_at)


async def list_windows(db: AsyncSession) -> list[TransferWindow]:
    result = await db.execute(select(TransferWindow).order_by(TransferWindow.opens_at.desc()))
    return list(result.scalars())


async def windows_for(db: AsyncSession, country: str | None) -> list[TransferWindow]:
    """The windows that govern clubs in `country`: its own, else the ones
    with no country. A handful of rows a year, so they're filtered here."""
    rows = await list_windows(db)
    own = [w for w in rows if w.country and _key(w.country) == _key(country)] if _key(country) else []
    return own or [w for w in rows if not _key(w.country)]


async def club_country(db: AsyncSession, club_id: uuid.UUID | None) -> str | None:
    if club_id is None:
        return None
    from app.clubs.models import Club

    return (await db.execute(select(Club.country).where(Club.id == club_id))).scalar_one_or_none()


def _current(windows: list[TransferWindow], now: datetime) -> TransferWindow | None:
    open_ = [w for w in windows if _window_is_open(w, now)]
    return max(open_, key=lambda w: _utc(w.opens_at)) if open_ else None


def _next(windows: list[TransferWindow], now: datetime) -> TransferWindow | None:
    later = [w for w in windows if _utc(w.opens_at) > now]
    return min(later, key=lambda w: _utc(w.opens_at)) if later else None


async def get_current_window(
    db: AsyncSession, country: str | None = None, now: datetime | None = None,
) -> TransferWindow | None:
    return _current(await windows_for(db, country), now or _now())


async def get_next_window(
    db: AsyncSession, country: str | None = None, now: datetime | None = None,
) -> TransferWindow | None:
    return _next(await windows_for(db, country), now or _now())


async def any_window_exists(db: AsyncSession, country: str | None = None) -> bool:
    return bool(await windows_for(db, country))


async def registration_open(db: AsyncSession, country: str | None) -> bool:
    """Whether a club in `country` can register a signing right now."""
    windows = await windows_for(db, country)
    return not windows or _current(windows, _now()) is not None


def waits_for_window(deal) -> bool:
    """A move between two clubs waits for a window. A free agent, or a player
    joining once his contract has run out, can be registered at any time."""
    from app.deals.models import DealType

    return deal.seller_club_id is not None and deal.deal_type not in (DealType.FREE_TRANSFER, DealType.PRE_CONTRACT)


def _day(dt: datetime) -> str:
    return f"{_utc(dt).day} {_utc(dt):%B %Y}"


async def completion_hold(db: AsyncSession, deal) -> str | None:
    """Why this deal can't complete yet, or None: the buying club can't
    register the player until its window opens. Talks and paperwork go on."""
    if not waits_for_window(deal):
        return None
    country = await club_country(db, deal.buyer_club_id)
    windows = await windows_for(db, country)
    now = _now()
    if not windows or _current(windows, now) is not None:
        return None
    nxt = _next(windows, now)
    where = f" in {country}" if country else ""
    if nxt is None:
        return (f"The transfer window{where} is closed, and no date is set for the next one. "
                "The deal can complete once it opens.")
    return (f"The transfer window{where} is closed. The deal can complete when "
            f"the {nxt.name} window opens on {_day(nxt.opens_at)}.")


async def hold_until(db: AsyncSession, deal) -> datetime | None:
    """When a held deal can complete: the next window's opening, if set."""
    if not waits_for_window(deal):
        return None
    windows = await windows_for(db, await club_country(db, deal.buyer_club_id))
    now = _now()
    if not windows or _current(windows, now) is not None:
        return None
    nxt = _next(windows, now)
    return _utc(nxt.opens_at) if nxt else None


async def coverage(db: AsyncSession) -> list[dict]:
    """For each country with clubs on TransferX: its current and next window,
    and whether it has none open or opening in the next six months (the
    admin's reminder to add the dates)."""
    from app.clubs.models import Club

    countries = sorted({c.strip() for c in (await db.execute(
        select(Club.country).where(Club.country.is_not(None)).distinct())).scalars() if c and c.strip()},
        key=str.casefold)
    now = _now()
    horizon = now + timedelta(days=COVERAGE_DAYS)
    out = []
    for country in countries:
        windows = await windows_for(db, country)
        current, nxt = _current(windows, now), _next(windows, now)
        own = any(w.country for w in windows)
        out.append({
            "country": country,
            "own_windows": own,
            "current": current,
            "next": nxt,
            "missing": current is None and (nxt is None or _utc(nxt.opens_at) > horizon),
        })
    return out


async def create_window(
    db: AsyncSession, name: str, opens_at: datetime, closes_at: datetime, *,
    country: str | None = None, source_url: str | None = None, checked_on: date | None = None,
) -> TransferWindow:
    w = TransferWindow(name=name, opens_at=opens_at, closes_at=closes_at, country=(country or "").strip() or None,
                       source_url=(source_url or "").strip() or None, checked_on=checked_on)
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


async def notify_opened_windows(db: AsyncSession) -> int:
    """Once a window opens, tell both clubs of every deal that was waiting
    for it that they can complete it now. Returns how many deals."""
    from app.clubs.models import Club
    from app.deals.models import Deal, DealStage, DealStatus
    from app.notifications.models import NotificationType
    from app.notifications.service import notify_club
    from app.players.models import Player

    now = _now()
    opened = [w for w in await list_windows(db) if w.opened_notice_at is None and _window_is_open(w, now)]
    if not opened:
        return 0
    waiting = (await db.execute(select(Deal).where(
        Deal.status == DealStatus.PENDING_COMPLETION, Deal.stage == DealStage.CONFIRMED))).scalars().all()
    countries = dict((await db.execute(select(Club.id, Club.country).where(
        Club.id.in_({d.buyer_club_id for d in waiting})))).all()) if waiting else {}
    names = dict((await db.execute(select(Player.id, Player.name).where(
        Player.id.in_({d.player_id for d in waiting})))).all()) if waiting else {}
    count = 0
    for w in opened:
        w.opened_notice_at = now
        for deal in waiting:
            if not waits_for_window(deal) or w not in await windows_for(db, countries.get(deal.buyer_club_id)):
                continue
            player = names.get(deal.player_id) or "the player"
            for club_id in (deal.buyer_club_id, deal.seller_club_id):
                if club_id is not None:
                    await notify_club(
                        db, club_id, type=NotificationType.DEAL_PAPERWORK,
                        message=f"The {w.name} window is open: {player}'s transfer can be completed now",
                        link=f"/deals/{deal.id}", related_player_id=deal.player_id,
                    )
            count += 1
    await db.flush()
    return count
