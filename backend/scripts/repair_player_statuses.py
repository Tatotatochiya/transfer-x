#!/usr/bin/env python
"""
Repair: re-derive every player's status where the stored one disagrees with
the rule (ADR 0003, players.service.normalize_player_status).

Why: 13 demo players have no club anywhere — no TransferX contract, no
`team_name`, no `world_team_id` — yet are stored as EXTERNAL ("contracted at a
club outside TransferX"). By the rule they are FREE_AGENT. As EXTERNAL they
cannot be signed, and TransferX or their agent cannot invite them to create an
account (ADR 0007), so free agents did not exist on the platform at all.

The status is set by `normalize_player_status` itself, not by hand, so this
repair can never disagree with the code that maintains status day to day.
That includes its side effect: a player who becomes a free agent triggers the
PLAYER_AVAILABLE notification to clubs watching for free agents, which is
right — they are newly available.

Idempotent: only mismatched players are touched, so a second run does nothing.

Usage (inside Docker):
    docker compose exec api python scripts/repair_player_statuses.py --dry-run
    docker compose exec api python scripts/repair_player_statuses.py
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

# Registers every model module before the mappers configure.
import backfill_demo_squad_contracts  # noqa: E402,F401

from app.config import settings  # noqa: E402
from app.players.models import Contract, Player, PlayerStatus  # noqa: E402
from app.players.service import has_external_club, normalize_player_status  # noqa: E402


def expected_status(player: Player, has_active_contract: bool) -> PlayerStatus:
    if has_active_contract:
        return PlayerStatus.CONTRACTED
    return PlayerStatus.EXTERNAL if has_external_club(player) else PlayerStatus.FREE_AGENT


async def main(dry_run: bool) -> None:
    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as db:
        contracted = set((await db.execute(
            select(Contract.player_id).where(Contract.is_active.is_(True))
        )).scalars())
        players = (await db.execute(select(Player))).scalars().all()
        mismatched = [p for p in players if p.status != expected_status(p, p.id in contracted)]

        for p in mismatched:
            before = p.status.value
            print(f"  {p.name}: {before} -> {expected_status(p, p.id in contracted).value}")
            if not dry_run:
                await normalize_player_status(db, p)
        print(f"Players checked: {len(players)}; mismatched: {len(mismatched)}")

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
