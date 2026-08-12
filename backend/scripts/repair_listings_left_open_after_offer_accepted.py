#!/usr/bin/env python
"""
Repair listings left OPEN after a direct offer against them was accepted.

`offers/service.py::accept_offer` created the deal but never closed the
originating listing, and never carried `offer.sale_id` onto `deal.sale_id`
(the auction path, `sales/service.py::accept_bid`, always did both). Result:
the player kept showing as "Listed" and the listing stayed publicly live while
their deal was already in progress — directly contradicting the deal banner's
own "New offers and sale listings are not permitted while a deal is active".

The code bug is fixed; this repairs rows created before that fix. Each repaired
row is provable, not a judgement call: the deal's own offer carries
`sale_id == sale.id`, so the listing is unambiguously the one that produced it.

Closing is delegated to sales_service.close_sale_after_offer_accepted() — the
same function accept_offer now calls — so any active bids are released and
their bidders notified rather than left with budget reserved against a dead
listing.

Idempotent: re-running finds nothing once repaired.

Usage (inside Docker):
    docker compose exec api python scripts/repair_listings_left_open_after_offer_accepted.py
    docker compose exec api python scripts/repair_listings_left_open_after_offer_accepted.py --dry-run
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

# Register every model before any query runs so relationship() forward-refs
# resolve — same reason scripts/seed_demo.py carries this block.
import app.agents.models  # noqa: F401
import app.analytics.models  # noqa: F401
import app.approvals.models  # noqa: F401
import app.audit.models  # noqa: F401
import app.auth.models  # noqa: F401
import app.clubs.models  # noqa: F401
import app.deals.models  # noqa: F401
import app.fixtures.models  # noqa: F401
import app.mandates.models  # noqa: F401
import app.notifications.models  # noqa: F401
import app.offers.models  # noqa: F401
import app.players.models  # noqa: F401
import app.sales.models  # noqa: F401
import app.scouting.models  # noqa: F401
import app.stats.models  # noqa: F401
import app.transfer_window.models  # noqa: F401
import app.valuation.models  # noqa: F401
import app.verification.models  # noqa: F401
import app.world.models  # noqa: F401

from app.config import settings
from app.deals.models import Deal, DealStatus
from app.offers.models import Offer
from app.players.models import Player
from app.sales import service as sales_service
from app.sales.models import Sale, SaleStatus

LIVE_DEAL_STATUSES = (DealStatus.IN_PROGRESS, DealStatus.PENDING_COMPLETION)


async def main(dry_run: bool) -> None:
    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as db:
        async with db.begin():
            rows = (
                await db.execute(
                    select(Sale, Deal, Player.name)
                    .join(Offer, Offer.sale_id == Sale.id)
                    .join(Deal, Deal.offer_id == Offer.id)
                    .join(Player, Player.id == Sale.player_id)
                    .where(
                        Sale.status == SaleStatus.OPEN,
                        Deal.status.in_(LIVE_DEAL_STATUSES),
                    )
                )
            ).all()

            if not rows:
                print("Nothing to repair — no listing is OPEN behind a live deal.")
                return

            print(f"Found {len(rows)} listing(s) left open behind a live deal:")
            for sale, deal, player_name in rows:
                print(f"  - {player_name}: sale {sale.id} (deal {deal.id}, stage {deal.stage.value})")

            if dry_run:
                print("\n--dry-run: no changes written.")
                return

            for sale, deal, _player_name in rows:
                deal.sale_id = sale.id  # restore the link the collapse path needs
                await sales_service.close_sale_after_offer_accepted(
                    db, sale.id, actor_club_id=sale.seller_club_id
                )

            print(f"\nRepaired {len(rows)} listing(s).")

    await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Report only, write nothing")
    args = parser.parse_args()
    asyncio.run(main(args.dry_run))
