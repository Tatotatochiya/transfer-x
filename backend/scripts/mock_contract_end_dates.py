#!/usr/bin/env python
"""
Development only: give every contracted player a mock contract end date.

Why: the demo data carries no contract end dates at all (no active contract has
`end_date`, no player has `contract_expiry`), so everything that reasons about
contracts running down shows nothing — the War Room's expiring contracts, the
morning briefing, "Who might want him?" and the pricing assistant's discount
for a player whose contract ends within a year. Real end dates should come from
the clubs or the vendor feed; until then this fills the gap so the features
can be demoed.

- Only missing dates are filled; a real date is never overwritten.
- Players at a TransferX club get it on their active contract and on the
  player record; players at clubs outside TransferX on the player record.
  Free agents have no contract and are left alone.
- Most dates fall on 30 June (the usual end of a football contract), spread
  so a squad has a realistic mix: about 5% ending on the next 31 January (a
  winter expiry, so the "expiring within six months" views have something to
  show), 10% this coming summer, 15% the next, then 30%, 25% and 15% over the
  following three.
- Deterministic by player id, so re-running gives the same dates.

Usage (inside Docker):
    docker compose exec api python scripts/mock_contract_end_dates.py --dry-run
    docker compose exec api python scripts/mock_contract_end_dates.py
"""

import argparse
import asyncio
import hashlib
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

# Registers every model module before the mappers configure.
import backfill_demo_squad_contracts  # noqa: E402,F401

from app.config import settings  # noqa: E402
from app.players.models import Contract, Player  # noqa: E402

# (cumulative share, summers from now); None = the next 31 January.
_SPREAD = [(0.05, None), (0.15, 0), (0.30, 1), (0.60, 2), (0.85, 3), (1.00, 4)]


def mock_end_date(player_id, today: date) -> date:
    """The next 31 January, or 30 June of a summer 0–4 years out, chosen by
    the player's id."""
    h = int(hashlib.sha256(str(player_id).encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
    summers = next(n for share, n in _SPREAD if h <= share)
    if summers is None:
        winter = date(today.year, 1, 31)
        return winter if winter > today else date(today.year + 1, 1, 31)
    first = date(today.year, 6, 30)
    if first <= today:
        first = date(today.year + 1, 6, 30)
    return date(first.year + summers, 6, 30)


async def main(dry_run: bool) -> None:
    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    today = date.today()

    async with session_factory() as db:
        contracts = list((await db.execute(
            select(Contract).where(Contract.is_active.is_(True), Contract.end_date.is_(None))
        )).scalars())
        for c in contracts:
            c.end_date = mock_end_date(c.player_id, today)
        by_player = {c.player_id: c.end_date for c in contracts}

        players = list((await db.execute(
            select(Player).where(
                Player.contract_expiry.is_(None),
                or_(Player.current_club_id.is_not(None), Player.team_name.is_not(None), Player.world_team_id.is_not(None)),
            )
        )).scalars())
        for p in players:
            p.contract_expiry = by_player.get(p.id) or mock_end_date(p.id, today)

        ends: dict[date, int] = {}
        for p in players:
            ends[p.contract_expiry] = ends.get(p.contract_expiry, 0) + 1
        print(f"Active contracts given an end date: {len(contracts)}")
        print(f"Players given contract_expiry:      {len(players)}")
        for d in sorted(ends):
            print(f"  ends {d.isoformat()}: {ends[d]}")

        if dry_run:
            await db.rollback()
            print("Dry run — nothing written.")
        else:
            await db.commit()
            print("Written.")
    await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    parser.add_argument("--dry-run", action="store_true")
    asyncio.run(main(parser.parse_args().dry_run))
