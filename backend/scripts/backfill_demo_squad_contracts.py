#!/usr/bin/env python
"""
One-off backfill: 80 players across the Liverpool/Chelsea/Arsenal demo clubs
had `current_club_id` set with no backing `Contract` row at all — a data
invariant violation (current_club_id is meant to be derived exclusively from
an active contract via players_service.normalize_player_status). Found while
investigating a "My Club" valuation display bug in the redesign session.

This creates one real contract per orphaned player, through the same
create_contract() service function the real "upload a contract" flow will
use — not a raw INSERT — so current_club_id re-derives consistently rather
than bypassing the invariant a second time.

Terms are a plausible (not literally random) spread: contract length weighted
toward the realistic 2-3 year range, wage scaled off the player's fair-value
model score where one exists (roughly value * 0.004/week, a rough real-world
value-to-wage ratio), a flat reasonable range otherwise. Deterministic by
seed, matching scripts/seed_demo.py's own convention.

Usage (inside Docker):
    docker compose exec api python scripts/backfill_demo_squad_contracts.py
"""

import asyncio
import random
import sys
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

# Every model module needs registering before any query runs, so relationship()
# string forward-refs (e.g. Player.current_club -> "Club") resolve — matches
# scripts/seed_demo.py's own import block for the same reason.
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
from app.players import service as players_service
from app.players.models import Contract, Player
from app.valuation import service as valuation_service

SEED = 42


def _generate_terms(fair_value: Decimal | None) -> tuple[date, date, Decimal]:
    length_years = random.choice([1, 2, 2, 3, 3, 3, 4, 5])
    years_remaining = random.uniform(0.5, length_years)
    end_date = date.today() + timedelta(days=int(years_remaining * 365))
    start_date = end_date - timedelta(days=int(length_years * 365))

    if fair_value:
        wage = float(fair_value) * 0.004 * random.uniform(0.7, 1.3)
    else:
        wage = random.uniform(3_000, 40_000)
    wage = max(1_000, round(wage / 500) * 500)

    return start_date, end_date, Decimal(str(wage))


async def main() -> None:
    random.seed(SEED)
    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as db:
        async with db.begin():
            result = await db.execute(
                select(Player).where(
                    Player.current_club_id.is_not(None),
                    ~Player.id.in_(select(Contract.player_id)),
                )
            )
            orphaned = list(result.scalars())
            print(f"Found {len(orphaned)} players with a club but no contract ever.")

            valuations = await valuation_service.get_latest_valuations(db, [p.id for p in orphaned])

            for player in orphaned:
                valuation_row = valuations.get(player.id)
                fair_value = valuation_row.fair_value if valuation_row else None
                start_date, end_date, wage = _generate_terms(fair_value)
                await players_service.create_contract(
                    db,
                    player,
                    club_id=player.current_club_id,
                    start_date=start_date,
                    end_date=end_date,
                    wage_weekly=wage,
                )

        print(f"Created {len(orphaned)} contracts.")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
