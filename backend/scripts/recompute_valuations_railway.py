"""One-shot script: recompute every player's fair-value valuation against Railway's DB.

Mirrors sync_leagues.py's pattern — connects to Railway's public Postgres directly
rather than needing to restart the live service (which only fires the scheduled
valuation_compute job ~15s after boot, once, per deploy).

Usage (local machine, with DATABASE_PUBLIC_URL from `railway variables -k`):
    DATABASE_PUBLIC_URL=postgresql://... python scripts/recompute_valuations_railway.py
"""
import asyncio
import os
import sys


async def main() -> None:
    public_url = os.environ.get("DATABASE_PUBLIC_URL")
    if public_url:
        os.environ["DATABASE_URL"] = public_url

    # ALL models must be imported so SQLAlchemy can resolve string-based relationships,
    # same reason migrations/env.py and sync_leagues.py carry their own import block.
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
    from app.agents.models import AgentDealInvitation, AgentCommission, NegotiationMessage  # noqa: F401
    from app.mandates.models import Mandate, ClientAlert  # noqa: F401
    from app.audit.models import AuditEvent  # noqa: F401
    from app.approvals.models import PendingApproval  # noqa: F401
    from app.valuation.models import PlayerValuation  # noqa: F401
    from app.valuation.service import compute_all_valuations

    async with AsyncSessionLocal() as db:
        async with db.begin():
            counts = await compute_all_valuations(db)
        print(f"updated={counts['updated']} skipped_ineligible={counts['skipped_ineligible']} errors={counts['errors']}")


if __name__ == "__main__":
    asyncio.run(main())
