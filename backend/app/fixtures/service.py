"""Fixture fetch + cache service.

Caching strategy: fixtures for a team are re-fetched from API-Football if
the newest cached record for that team is older than CACHE_TTL_SECONDS.
This prevents hammering the API on every page load while keeping data fresh.
"""
import uuid
from datetime import datetime, timezone, timedelta

from sqlalchemy import select, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.vendor.client import ApiFootballClient, VENDOR
from app.fixtures.models import Fixture
from app.world import service as world_service

CACHE_TTL_SECONDS = 3600  # 1 hour


async def _is_cache_fresh(db: AsyncSession, vendor_team_id: int) -> bool:
    """Return True if we have fixture data for this team fetched within the TTL."""
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=CACHE_TTL_SECONDS)
    result = await db.execute(
        select(func.max(Fixture.fetched_at)).where(
            or_(
                Fixture.home_team_vendor_id == vendor_team_id,
                Fixture.away_team_vendor_id == vendor_team_id,
            )
        )
    )
    newest = result.scalar()
    if newest is None:
        return False
    # Ensure timezone-aware comparison
    if newest.tzinfo is None:
        newest = newest.replace(tzinfo=timezone.utc)
    return newest > cutoff


def _parse_fixture(raw: dict, now: datetime) -> dict:
    fixture_info = raw.get("fixture", {})
    league_info = raw.get("league", {})
    teams = raw.get("teams", {})
    goals = raw.get("goals", {})
    status = fixture_info.get("status", {})
    venue = fixture_info.get("venue") or {}

    date_str = fixture_info.get("date")
    kickoff_at = None
    if date_str:
        try:
            kickoff_at = datetime.fromisoformat(date_str)
        except ValueError:
            pass

    return {
        "id": uuid.uuid4(),
        "vendor": VENDOR,
        "fixture_vendor_id": fixture_info.get("id"),
        "league_id": league_info.get("id"),
        "season": league_info.get("season"),
        "league_name": league_info.get("name"),
        "round": league_info.get("round"),
        "home_team_vendor_id": teams.get("home", {}).get("id"),
        "away_team_vendor_id": teams.get("away", {}).get("id"),
        "home_team_name": teams.get("home", {}).get("name", ""),
        "away_team_name": teams.get("away", {}).get("name", ""),
        "home_team_crest_url": teams.get("home", {}).get("logo"),
        "away_team_crest_url": teams.get("away", {}).get("logo"),
        "kickoff_at": kickoff_at,
        "status_short": status.get("short", "NS"),
        "status_long": status.get("long"),
        "home_goals": goals.get("home"),
        "away_goals": goals.get("away"),
        "venue_name": venue.get("name"),
        "fetched_at": now,
    }


async def _fetch_and_store(
    db: AsyncSession,
    client: ApiFootballClient,
    vendor_team_id: int,
    next_count: int,
    last_count: int,
) -> None:
    now = datetime.now(timezone.utc)
    rows: list[dict] = []
    # Collect unique teams seen across all fixtures for WorldTeam upsert
    teams_seen: dict[int, dict] = {}

    for params in [
        {"team": vendor_team_id, "next": next_count},
        {"team": vendor_team_id, "last": last_count},
    ]:
        data = await client._get("/fixtures", params)
        for raw in data.get("response", []):
            parsed = _parse_fixture(raw, now)
            if parsed["fixture_vendor_id"] and parsed["home_team_vendor_id"] and parsed["away_team_vendor_id"]:
                rows.append(parsed)
                # Collect home and away team info for WorldTeam upsert
                teams_info = raw.get("teams", {})
                league_info = raw.get("league", {})
                for side in ("home", "away"):
                    t = teams_info.get(side, {})
                    tid = t.get("id")
                    if tid and tid not in teams_seen:
                        teams_seen[tid] = {
                            "vendor_id": str(tid),
                            "name": t.get("name", ""),
                            "crest_url": t.get("logo"),
                            "league_name": league_info.get("name"),
                            "country": league_info.get("country"),
                        }

    if not rows:
        return

    # Upsert world teams so fixture team names are navigable
    for team_data in teams_seen.values():
        await world_service.upsert_world_team(
            db,
            vendor=VENDOR,
            vendor_id=team_data["vendor_id"],
            name=team_data["name"],
            crest_url=team_data["crest_url"],
            league_name=team_data["league_name"],
            country=team_data["country"],
        )

    # Upsert fixtures — on conflict update mutable fields
    stmt = pg_insert(Fixture).values(rows)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_fixtures_vendor_fixture_id",
        set_={
            "status_short": stmt.excluded.status_short,
            "status_long": stmt.excluded.status_long,
            "home_goals": stmt.excluded.home_goals,
            "away_goals": stmt.excluded.away_goals,
            "kickoff_at": stmt.excluded.kickoff_at,
            "round": stmt.excluded.round,
            "fetched_at": stmt.excluded.fetched_at,
        },
    )
    await db.execute(stmt)


async def get_team_fixtures(
    db: AsyncSession,
    vendor_team_id: int,
    client: ApiFootballClient,
    next_count: int = 5,
    last_count: int = 5,
) -> list[Fixture]:
    """Return cached fixtures, refreshing from the API if cache is stale."""
    if not await _is_cache_fresh(db, vendor_team_id):
        await _fetch_and_store(db, client, vendor_team_id, next_count, last_count)
        await db.commit()

    result = await db.execute(
        select(Fixture)
        .where(
            or_(
                Fixture.home_team_vendor_id == vendor_team_id,
                Fixture.away_team_vendor_id == vendor_team_id,
            )
        )
        .order_by(Fixture.kickoff_at.asc().nulls_last())
    )
    return list(result.scalars().all())
