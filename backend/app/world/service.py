"""M6 — World service layer."""

import uuid

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.world.models import WorldLeague, WorldTeam


# ── WorldTeam ──────────────────────────────────────────────────────────────────

async def list_world_teams(
    db: AsyncSession,
    *,
    search: str | None = None,
    country: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[WorldTeam], int]:
    q = select(WorldTeam).order_by(WorldTeam.name)
    if search:
        q = q.where(WorldTeam.name.ilike(f"%{search}%"))
    if country:
        q = q.where(WorldTeam.country.ilike(f"%{country}%"))
    total_q = select(func.count()).select_from(q.subquery())
    total = (await db.execute(total_q)).scalar_one()
    q = q.offset((page - 1) * page_size).limit(page_size)
    rows = (await db.execute(q)).scalars().all()
    return list(rows), total


async def get_world_team_by_id(db: AsyncSession, team_id: uuid.UUID) -> WorldTeam | None:
    result = await db.execute(select(WorldTeam).where(WorldTeam.id == team_id))
    return result.scalar_one_or_none()


async def get_world_team_by_vendor_id(
    db: AsyncSession, vendor: str, vendor_id: str
) -> WorldTeam | None:
    result = await db.execute(
        select(WorldTeam).where(
            WorldTeam.vendor == vendor,
            WorldTeam.vendor_id == vendor_id,
        )
    )
    return result.scalar_one_or_none()


async def upsert_world_team(
    db: AsyncSession,
    *,
    vendor: str,
    vendor_id: str,
    name: str,
    country: str | None = None,
    league_name: str | None = None,
    crest_url: str | None = None,
    season: str | None = None,
) -> WorldTeam:
    result = await db.execute(
        select(WorldTeam).where(
            WorldTeam.vendor == vendor,
            WorldTeam.vendor_id == vendor_id,
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        existing.name = name
        if country is not None:
            existing.country = country
        if league_name is not None:
            existing.league_name = league_name
        if crest_url is not None:
            existing.crest_url = crest_url
        if season is not None:
            existing.season = season
        await db.flush()
        return existing
    team = WorldTeam(
        vendor=vendor,
        vendor_id=vendor_id,
        name=name,
        country=country,
        league_name=league_name,
        crest_url=crest_url,
        season=season,
    )
    db.add(team)
    await db.flush()
    return team


async def list_leagues(
    db: AsyncSession,
    *,
    vendor: str | None = None,
    country: str | None = None,
    season: str | None = None,
    search: str | None = None,
) -> list[WorldLeague]:
    q = select(WorldLeague).order_by(WorldLeague.name)
    if vendor is not None:
        q = q.where(WorldLeague.vendor == vendor)
    if country is not None:
        q = q.where(WorldLeague.country == country)
    if season is not None:
        q = q.where(WorldLeague.season == season)
    if search is not None:
        q = q.where(WorldLeague.name.ilike(f"%{search}%"))
    result = await db.execute(q)
    return list(result.scalars())


async def get_league_by_id(db: AsyncSession, league_id: uuid.UUID) -> WorldLeague | None:
    result = await db.execute(select(WorldLeague).where(WorldLeague.id == league_id))
    return result.scalar_one_or_none()


async def upsert_league(
    db: AsyncSession,
    *,
    vendor: str,
    league_id: str,
    name: str,
    country: str | None = None,
    season: str | None = None,
) -> WorldLeague:
    """Insert or update a WorldLeague by (vendor, league_id) uniqueness."""
    result = await db.execute(
        select(WorldLeague).where(
            WorldLeague.vendor == vendor,
            WorldLeague.league_id == league_id,
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        existing.name = name
        if country is not None:
            existing.country = country
        if season is not None:
            existing.season = season
        await db.flush()
        return existing
    else:
        league = WorldLeague(
            vendor=vendor,
            league_id=league_id,
            name=name,
            country=country,
            season=season,
        )
        db.add(league)
        await db.flush()
        return league
