"""Backfill 2025 season data from API-Football for the top 5 European leagues.

Usage:
    python backfill_2025.py
"""

import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.config import settings
from app.database import AsyncSessionLocal

# Import all models so SQLAlchemy can resolve cross-model relationships
import app.auth.models  # noqa: F401
import app.clubs.models  # noqa: F401
import app.players.models  # noqa: F401
import app.sales.models  # noqa: F401
import app.offers.models  # noqa: F401
import app.deals.models  # noqa: F401
import app.scouting.models  # noqa: F401
import app.notifications.models  # noqa: F401
import app.stats.models  # noqa: F401
import app.world.models  # noqa: F401

from app.vendor.client import ApiFootballClient
from app.vendor.sync import sync_league, compute_all_form

TOP5_LEAGUES = [
    (39,  "Premier League"),
    (140, "La Liga"),
    (135, "Serie A"),
    (78,  "Bundesliga"),
    (61,  "Ligue 1"),
]

SEASON = 2025
SLEEP_MS = 300  # ms between pages — safe for paid plans, increase to 2000 for free tier


async def main() -> None:
    if not settings.apisports_key:
        print("ERROR: APISPORTS_KEY not set in .env")
        sys.exit(1)

    client = ApiFootballClient(settings.apisports_key, settings.api_football_base_url)

    total_created = 0
    total_updated = 0
    total_snapshots = 0

    for league_id, league_name in TOP5_LEAGUES:
        print(f"\n[{league_name}] league_id={league_id}, season={SEASON} ...")
        t0 = time.monotonic()
        async with AsyncSessionLocal() as db:
            async with db.begin():
                try:
                    result = await sync_league(db, league_id, SEASON, client, sleep_ms=SLEEP_MS)
                    elapsed = time.monotonic() - t0
                    print(
                        f"  players created={result['players_created']}  "
                        f"updated={result['players_updated']}  "
                        f"snapshots={result['snapshots_created']}  "
                        f"pages={result['pages_synced']}  "
                        f"({elapsed:.1f}s)"
                    )
                    total_created += result["players_created"]
                    total_updated += result["players_updated"]
                    total_snapshots += result["snapshots_created"]
                except Exception as exc:
                    elapsed = time.monotonic() - t0
                    print(f"  ERROR after {elapsed:.1f}s: {exc}")

    print(f"\n[Summary] players created={total_created}  updated={total_updated}  snapshots={total_snapshots}")

    print("\n[Form] Computing form scores ...")
    t0 = time.monotonic()
    async with AsyncSessionLocal() as db:
        async with db.begin():
            count = await compute_all_form(db, window_games=5)
    print(f"  {count} player form records updated  ({time.monotonic() - t0:.1f}s)")

    print("\nDone!")


if __name__ == "__main__":
    asyncio.run(main())
