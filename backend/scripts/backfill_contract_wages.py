#!/usr/bin/env python
"""
One-off backfill: give every active contract with no wage a plausible one, and
put that wage on its club's wage bill.

Why: a loan's wage share is now read from the player's contract instead of
being typed by the borrowing club (docs/feature_spec/loan-transfers.md,
deviation 24). Every active contract in the demo data has `wage_weekly` null —
`backfill_demo_squad_contracts.py` only created contracts for players who had
none, and the contracts that already existed never carried a wage. With no
wage on record a loan is refused, so without this no demo loan can be made.

The wage is also added to the club's `wage_reserved_weekly`, which is the
running wage bill (`_complete_deal` adds a signing's wage there). Filling the
contract alone would leave the two disagreeing, and a loan's return — which
gives the parent back the share it was relieved of — would hand the parent a
reservation it never carried.

Wages use the same model as backfill_demo_squad_contracts.py (fair value x
0.004/week where the valuation model has a figure, a flat range otherwise),
deterministic by seed. Idempotent: only contracts with no wage are touched, so
a second run does nothing.

Usage (inside Docker):
    docker compose exec api python scripts/backfill_contract_wages.py --dry-run
    docker compose exec api python scripts/backfill_contract_wages.py
"""

import argparse
import asyncio
import random
import sys
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

# Registers every model module (see that script's note on forward-refs) and
# provides the wage model, so both backfills price players the same way.
from backfill_demo_squad_contracts import SEED, _generate_terms  # noqa: E402

from app.clubs.models import ClubFinance  # noqa: E402
from app.config import settings  # noqa: E402
from app.players.models import Contract  # noqa: E402
from app.valuation import service as valuation_service  # noqa: E402


async def main(dry_run: bool) -> None:
    random.seed(SEED)
    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as db:
        if True:  # one transaction: committed at the end, or rolled back on --dry-run
            contracts = list((await db.execute(
                select(Contract)
                .where(
                    Contract.is_active == True,  # noqa: E712
                    or_(Contract.wage_weekly.is_(None), Contract.wage_weekly == 0),
                )
                .order_by(Contract.id)
            )).scalars())
            print(f"Found {len(contracts)} active contracts with no wage.")

            valuations = await valuation_service.get_latest_valuations(
                db, [c.player_id for c in contracts]
            )
            per_club: dict = defaultdict(Decimal)
            for contract in contracts:
                row = valuations.get(contract.player_id)
                _, _, wage = _generate_terms(row.fair_value if row else None)
                contract.wage_weekly = wage
                per_club[contract.club_id] += wage

            for club_id, total in per_club.items():
                fin = (await db.execute(
                    select(ClubFinance).where(ClubFinance.club_id == club_id)
                )).scalar_one_or_none()
                if fin is None:
                    print(f"  club {club_id}: no finance row, wage bill not updated")
                    continue
                print(
                    f"  club {club_id}: +£{total:,.0f}/wk wage bill "
                    f"(budget £{fin.wage_budget_total_weekly:,.0f}/wk)"
                )
                fin.wage_reserved_weekly += total

            if dry_run:
                await db.rollback()
                print("Dry run: nothing written.")
            else:
                await db.commit()
                print(f"Wrote wages to {len(contracts)} contracts.")

    await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--dry-run", action="store_true")
    asyncio.run(main(parser.parse_args().dry_run))
