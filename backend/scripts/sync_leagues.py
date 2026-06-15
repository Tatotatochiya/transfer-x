"""One-shot script: sync main leagues for a given season against Railway DB.

Usage (local with Railway env vars):
    railway run python scripts/sync_leagues.py

Reads DATABASE_URL and APISPORTS_KEY from environment (injected by `railway run`).
"""
import asyncio
import sys

# Main leagues to sync: (name, league_id)
LEAGUES = [
    ("Premier League",      39),
    ("La Liga",            140),
    ("Serie A",            135),
    ("Bundesliga",          78),
    ("Ligue 1",             61),
    ("Champions League",     2),
    ("Europa League",        3),
]
SEASON = 2025
SLEEP_MS = 200  # Be polite to the API — 200 ms between player fetches


async def main() -> None:
    import os

    # railway run injects DATABASE_URL as the internal hostname (only reachable inside
    # Railway's private network). Override with DATABASE_PUBLIC_URL when available so
    # this script can connect from a local machine.
    public_url = os.environ.get("DATABASE_PUBLIC_URL")
    if public_url:
        # app.config reads DATABASE_URL; swap it before import
        os.environ["DATABASE_URL"] = public_url

    # Import here so Railway env vars are already set before config is read.
    # ALL models must be imported so SQLAlchemy can resolve string-based relationships.
    from app.config import settings
    from app.database import AsyncSessionLocal, Base  # noqa: F401
    from app.auth.models import RefreshToken, User  # noqa: F401
    from app.clubs.models import Club, ClubFinance  # noqa: F401
    from app.deals.models import Deal, DealNote  # noqa: F401
    from app.fixtures.models import Fixture  # noqa: F401
    from app.notifications.models import Notification, NotificationPreference  # noqa: F401
    from app.offers.models import Offer, OfferEvent, OfferMessage  # noqa: F401
    from app.players.models import Contract, Player, PlayerInjury, PlayerTransfer  # noqa: F401
    from app.sales.models import Bid, Sale, SaleEvent  # noqa: F401
    from app.scouting.models import PlayerInterest, Shortlist, ShortlistItem  # noqa: F401
    from app.stats.models import PlayerForm, PlayerStats, PlayerStatsSnapshot, VendorSyncState  # noqa: F401
    from app.world.models import WorldLeague, WorldTeam  # noqa: F401
    from app.analytics.models import AnalyticsEvent  # noqa: F401
    from app.transfer_window.models import TransferWindow  # noqa: F401
    from app.vendor.client import ApiFootballClient
    from app.vendor.sync import sync_league

    if not settings.apisports_key:
        print("ERROR: APISPORTS_KEY not set in environment", file=sys.stderr)
        sys.exit(1)

    client = ApiFootballClient(settings.apisports_key, settings.api_football_base_url)

    for name, league_id in LEAGUES:
        print(f"\n{'='*60}")
        print(f"Syncing {name} (league_id={league_id}, season={SEASON}) ...")
        try:
            async with AsyncSessionLocal() as db:
                result = await sync_league(
                    db,
                    league_id=league_id,
                    season=SEASON,
                    client=client,
                    sleep_ms=SLEEP_MS,
                    created_by_user_id=None,
                )
                await db.commit()
            print(f"  OK — {result}")
        except Exception as exc:
            print(f"  FAILED: {exc}", file=sys.stderr)

    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(main())
