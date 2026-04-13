#!/usr/bin/env python
"""
Populate world_teams from existing player_stats data and API-Football.

1. Extracts distinct (vendor_id, team_name) pairs from player_stats.
2. Fetches team details (logo, country) from API-Football /teams endpoint.
3. Upserts WorldTeam records.
4. Links each Player.world_team_id to their team via player_stats.team_vendor_id.

Usage (inside Docker):
    docker compose exec api python scripts/populate_world_teams.py

Usage (local venv, from backend/ dir):
    python scripts/populate_world_teams.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.vendor.client import VENDOR

# Import all models so SQLAlchemy can resolve all relationships before any query runs
from app.auth.models import RefreshToken, User  # noqa: F401
from app.clubs.models import Club, ClubFinance  # noqa: F401
from app.deals.models import Deal, DealNote  # noqa: F401
from app.notifications.models import Notification  # noqa: F401
from app.offers.models import Offer, OfferEvent, OfferMessage  # noqa: F401
from app.players.models import Contract, Player  # noqa: F401
from app.sales.models import Bid, Sale, SaleEvent  # noqa: F401
from app.scouting.models import PlayerInterest, Shortlist, ShortlistItem  # noqa: F401
from app.stats.models import PlayerForm, PlayerStats, PlayerStatsSnapshot, VendorSyncState  # noqa: F401
from app.world.models import WorldLeague, WorldTeam  # noqa: F401


async def fetch_team_info(api_key: str, team_vendor_id: str) -> dict | None:
    """Fetch team logo + country from API-Football /teams endpoint."""
    url = "https://v3.football.api-sports.io/teams"
    headers = {"x-apisports-key": api_key}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers=headers, params={"id": team_vendor_id})
            if resp.status_code != 200:
                return None
            data = resp.json()
            items = data.get("response", [])
            if not items:
                return None
            t = items[0]
            team_data = t.get("team", {})
            venue_data = t.get("venue", {})
            return {
                "name": team_data.get("name"),
                "country": team_data.get("country"),
                "crest_url": team_data.get("logo"),
                "city": venue_data.get("city"),
            }
    except Exception as e:
        print(f"  API error for team {team_vendor_id}: {e}")
        return None


async def main() -> None:
    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    api_key = settings.apisports_key
    if not api_key:
        print("ERROR: APISPORTS_KEY not set in environment.")
        sys.exit(1)

    async with session_factory() as db:
        # 1. Collect distinct (team_vendor_id, team_name, league_id) pairs
        result = await db.execute(
            select(
                PlayerStats.team_vendor_id,
                PlayerStats.team_name,
                PlayerStats.league_id,
                PlayerStats.season,
            )
            .where(PlayerStats.team_vendor_id.isnot(None))
            .where(PlayerStats.team_name.isnot(None))
            .distinct()
        )
        rows = result.all()

        # Aggregate: pick the most common league_name per vendor_id
        from collections import defaultdict
        vendor_data: dict[str, dict] = {}
        league_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

        for team_vendor_id, team_name, league_id, season in rows:
            vid = str(team_vendor_id)
            if vid not in vendor_data:
                vendor_data[vid] = {"name": team_name, "season": season}
            if league_id:
                league_counts[vid][league_id] += 1

        print(f"Found {len(vendor_data)} distinct vendor teams in player_stats.")

        # 2. Fetch team info from API and upsert WorldTeam records
        # Fetch league names from world_leagues
        from app.world.models import WorldLeague
        leagues_result = await db.execute(select(WorldLeague))
        league_map: dict[str, str] = {}  # league_id → league_name
        for wl in leagues_result.scalars():
            league_map[str(wl.league_id)] = wl.name

        created = 0
        updated = 0

        for i, (vendor_id_str, data) in enumerate(vendor_data.items(), 1):
            team_name = data["name"]
            season = data["season"]

            # Find most-common league for this team
            top_league_id = max(league_counts[vendor_id_str], key=league_counts[vendor_id_str].get, default=None) if league_counts[vendor_id_str] else None
            league_name = league_map.get(top_league_id) if top_league_id else None

            print(f"[{i}/{len(vendor_data)}] {team_name} (vendor_id={vendor_id_str}) ...", end=" ", flush=True)

            # Check if already exists
            existing = (await db.execute(
                select(WorldTeam).where(
                    WorldTeam.vendor == VENDOR,
                    WorldTeam.vendor_id == vendor_id_str,
                )
            )).scalar_one_or_none()

            # Fetch fresh crest/country from API only if we don't have it yet
            if existing and existing.crest_url:
                api_info = None
                print("exists (skipping API call)")
            else:
                api_info = await fetch_team_info(api_key, vendor_id_str)
                print(f"fetched logo={'yes' if api_info and api_info.get('crest_url') else 'no'}")

            crest_url = (api_info or {}).get("crest_url") or (existing.crest_url if existing else None)
            country = (api_info or {}).get("country") or (existing.country if existing else None)

            if existing:
                existing.name = team_name
                if crest_url:
                    existing.crest_url = crest_url
                if country:
                    existing.country = country
                if league_name:
                    existing.league_name = league_name
                if season:
                    existing.season = season
                updated += 1
            else:
                wt = WorldTeam(
                    vendor=VENDOR,
                    vendor_id=vendor_id_str,
                    name=team_name,
                    country=country,
                    league_name=league_name,
                    crest_url=crest_url,
                    season=season,
                )
                db.add(wt)
                created += 1

            await db.flush()

            # Throttle to avoid hitting rate limits (100 req/day on free plan)
            if api_info is not None:
                await asyncio.sleep(0.5)

        await db.commit()
        print(f"\nWorldTeam: {created} created, {updated} updated.")

        # 3. Link players to their world team via player_stats.team_vendor_id
        print("\nLinking players to world teams...")
        wt_result = await db.execute(
            select(WorldTeam.id, WorldTeam.vendor_id).where(WorldTeam.vendor == VENDOR)
        )
        vendor_to_wt_id = {row.vendor_id: row.id for row in wt_result}

        # Update players: set world_team_id by matching player_stats.team_vendor_id
        linked = 0
        from app.players.models import Player
        players_with_stats = await db.execute(
            select(
                PlayerStats.player_id,
                PlayerStats.team_vendor_id,
            )
            .where(PlayerStats.team_vendor_id.isnot(None))
            .distinct(PlayerStats.player_id)
        )
        for player_id, team_vendor_id in players_with_stats:
            wt_id = vendor_to_wt_id.get(str(team_vendor_id))
            if wt_id:
                await db.execute(
                    update(Player)
                    .where(Player.id == player_id)
                    .where(Player.world_team_id.is_(None))  # don't overwrite manually set links
                    .values(world_team_id=wt_id)
                )
                linked += 1

        await db.commit()
        print(f"Linked {linked} players to world teams.")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
