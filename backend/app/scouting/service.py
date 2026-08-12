"""M5 — Scouting service layer."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.scouting.models import InterestLevel, InterestStage, PlayerInterest, Shortlist, ShortlistItem


# ── Shortlists ────────────────────────────────────────────────────────────────


async def list_shortlists(db: AsyncSession, club_id: uuid.UUID) -> list[Shortlist]:
    result = await db.execute(
        select(Shortlist)
        .where(Shortlist.club_id == club_id)
        .options(selectinload(Shortlist.items).selectinload(ShortlistItem.player))
        .order_by(Shortlist.name)
    )
    return list(result.scalars())


async def get_shortlist_by_id(db: AsyncSession, shortlist_id: uuid.UUID) -> Shortlist | None:
    result = await db.execute(
        select(Shortlist)
        .where(Shortlist.id == shortlist_id)
        .options(selectinload(Shortlist.items).selectinload(ShortlistItem.player))
    )
    return result.scalar_one_or_none()


async def create_shortlist(
    db: AsyncSession, *, club_id: uuid.UUID, name: str, description: str | None = None
) -> Shortlist:
    # Check for name uniqueness within club
    existing = await db.execute(
        select(Shortlist).where(Shortlist.club_id == club_id, Shortlist.name == name)
    )
    if existing.scalar_one_or_none():
        raise ValueError(f"Shortlist named '{name}' already exists")

    sl = Shortlist(club_id=club_id, name=name, description=description)
    db.add(sl)
    await db.flush()
    return sl


async def update_shortlist(
    db: AsyncSession, shortlist: Shortlist, *, name: str | None, description: str | None
) -> Shortlist:
    if name is not None:
        name = name.strip()
        if not name:
            raise ValueError("name cannot be empty")
        # Check uniqueness if name is changing
        if name != shortlist.name:
            existing = await db.execute(
                select(Shortlist).where(
                    Shortlist.club_id == shortlist.club_id, Shortlist.name == name
                )
            )
            if existing.scalar_one_or_none():
                raise ValueError(f"Shortlist named '{name}' already exists")
        shortlist.name = name
    if description is not None:
        shortlist.description = description
    await db.flush()
    return shortlist


async def delete_shortlist(db: AsyncSession, shortlist: Shortlist) -> None:
    await db.delete(shortlist)
    await db.flush()


# ── Shortlist items ───────────────────────────────────────────────────────────


async def add_to_shortlist(
    db: AsyncSession,
    *,
    shortlist_id: uuid.UUID,
    player_id: uuid.UUID,
    priority: int = 3,
    notes: str | None = None,
) -> ShortlistItem:
    existing = await db.execute(
        select(ShortlistItem).where(
            ShortlistItem.shortlist_id == shortlist_id,
            ShortlistItem.player_id == player_id,
        )
    )
    if existing.scalar_one_or_none():
        raise ValueError("Player is already on this shortlist")

    item = ShortlistItem(
        shortlist_id=shortlist_id,
        player_id=player_id,
        priority=priority,
        notes=notes,
    )
    db.add(item)
    await db.flush()
    return item


async def get_shortlist_item(
    db: AsyncSession, shortlist_id: uuid.UUID, player_id: uuid.UUID
) -> ShortlistItem | None:
    result = await db.execute(
        select(ShortlistItem)
        .where(ShortlistItem.shortlist_id == shortlist_id, ShortlistItem.player_id == player_id)
        .options(selectinload(ShortlistItem.player))
    )
    return result.scalar_one_or_none()


async def update_shortlist_item(
    db: AsyncSession, item: ShortlistItem, *, priority: int | None, notes: str | None
) -> ShortlistItem:
    if priority is not None:
        item.priority = priority
    if notes is not None:
        item.notes = notes
    await db.flush()
    return item


async def remove_from_shortlist(db: AsyncSession, item: ShortlistItem) -> None:
    await db.delete(item)
    await db.flush()


# ── Player interests ──────────────────────────────────────────────────────────


async def list_interests(db: AsyncSession, club_id: uuid.UUID) -> list[PlayerInterest]:
    result = await db.execute(
        select(PlayerInterest)
        .where(PlayerInterest.club_id == club_id)
        .options(selectinload(PlayerInterest.player))
        .order_by(PlayerInterest.last_touched_at.desc())
    )
    return list(result.scalars())


async def get_interest(
    db: AsyncSession, club_id: uuid.UUID, player_id: uuid.UUID
) -> PlayerInterest | None:
    result = await db.execute(
        select(PlayerInterest)
        .where(PlayerInterest.club_id == club_id, PlayerInterest.player_id == player_id)
        .options(selectinload(PlayerInterest.player))
    )
    return result.scalar_one_or_none()


async def set_interest(
    db: AsyncSession,
    *,
    club_id: uuid.UUID,
    player_id: uuid.UUID,
    level: InterestLevel,
    stage: InterestStage,
    notes: str | None = None,
) -> PlayerInterest:
    """Upsert a PlayerInterest record."""
    interest = await get_interest(db, club_id, player_id)
    if interest:
        interest.level = level
        interest.stage = stage
        if notes is not None:
            interest.notes = notes
    else:
        interest = PlayerInterest(
            club_id=club_id,
            player_id=player_id,
            level=level,
            stage=stage,
            notes=notes,
        )
        db.add(interest)
    await db.flush()
    return interest


async def clear_interest(db: AsyncSession, interest: PlayerInterest) -> None:
    await db.delete(interest)
    await db.flush()


# ── Targets dashboard ─────────────────────────────────────────────────────────


async def get_targets(db: AsyncSession, club_id: uuid.UUID) -> list[dict]:
    """Return consolidated target players (shortlisted + interested), deduplicated."""
    from app.players.models import Player

    # Collect all player_ids from shortlists
    shortlists = await list_shortlists(db, club_id)
    interests = await list_interests(db, club_id)

    # Build per-player data
    player_map: dict[uuid.UUID, dict] = {}

    for sl in shortlists:
        for item in sl.items:
            pid = item.player_id
            if pid not in player_map:
                player_map[pid] = {
                    "player": item.player,
                    "on_shortlists": [],
                    "interest_level": None,
                    "interest_stage": None,
                }
            player_map[pid]["on_shortlists"].append(sl.name)

    for interest in interests:
        pid = interest.player_id
        if pid not in player_map:
            player_map[pid] = {
                "player": interest.player,
                "on_shortlists": [],
                "interest_level": None,
                "interest_stage": None,
            }
        player_map[pid]["interest_level"] = interest.level.value
        player_map[pid]["interest_stage"] = interest.stage.value

    targets = []
    for pid, data in player_map.items():
        p = data["player"]
        if p is None:
            continue
        # ADR 0003: the stored status is now trustworthy — a vendor player with
        # a real-world club is EXTERNAL, not FREE_AGENT — so the display-layer
        # override that used to live here has been removed rather than
        # duplicated. This was the only place the problem was compensated for.
        targets.append({
            "player_id": pid,
            "name": p.name,
            "position": p.position.value if p.position else None,
            "status": p.status.value,
            "open_to_offers": p.open_to_offers,
            "on_shortlists": data["on_shortlists"],
            "interest_level": data["interest_level"],
            "interest_stage": data["interest_stage"],
        })

    return targets
