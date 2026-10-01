#!/usr/bin/env python
"""
Development / demo: give every TransferX player an agent.

Every player a deal can happen for (CONTRACTED at a club on TransferX, or a
FREE_AGENT) who has no active mandate is given an exclusive mandate with one
of the existing agents, through the same `mandates.service.create_mandate`
the app uses (which also sets `players.agent_id`). Players are shared out
evenly: shuffled with a fixed seed, then dealt to the agents in turn. A
mandate runs two years from today, the longest a representation contract
may run under FIFA's agent regulations.

What it changes in practice: a new deal for one of these players now
starts at the agent negotiation stage and invites his agent, and his agent
answers personal terms (ADR 0007). Deals already under way are left alone.
Players at clubs outside TransferX are not touched.

Idempotent: a player with any active mandate is skipped. One transaction;
--dry-run prints the share-out and writes nothing.

Usage (inside Docker, or a shell on the Railway API service):
    python scripts/allocate_players_to_agents.py --dry-run
    python scripts/allocate_players_to_agents.py
"""

import argparse
import asyncio
import random
import sys
from collections import Counter
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import backfill_demo_squad_contracts  # noqa: F401,E402  (registers every model)
from app.auth.models import AgentProfile, User  # noqa: E402
from app.config import settings  # noqa: E402
from app.mandates import service as mandates_service  # noqa: E402
from app.mandates.models import Mandate, MandateStatus  # noqa: E402
from app.players.models import Player, PlayerStatus  # noqa: E402

SEED = 2026
MANDATE_YEARS = 2


async def main(dry_run: bool) -> None:
    random.seed(SEED)
    today = date.today()
    end = date(today.year + MANDATE_YEARS, today.month, min(today.day, 28))
    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as db:
        agents = (await db.execute(
            select(AgentProfile).join(User, User.id == AgentProfile.user_id)
            .where(User.is_active.is_(True)).order_by(AgentProfile.created_at)
        )).scalars().all()
        if not agents:
            print("No active agents on TransferX — nothing to allocate.")
            await engine.dispose()
            return

        represented = set((await db.execute(
            select(Mandate.player_id).where(Mandate.status == MandateStatus.ACTIVE)
        )).scalars())
        players = (await db.execute(
            select(Player).where(Player.status.in_([PlayerStatus.CONTRACTED, PlayerStatus.FREE_AGENT]))
            .order_by(Player.name, Player.id)
        )).scalars().all()
        todo = [p for p in players if p.id not in represented]
        random.shuffle(todo)

        per_agent: Counter = Counter()
        for i, player in enumerate(todo):
            agent = agents[i % len(agents)]
            await mandates_service.create_mandate(
                db, agent_profile_id=agent.id, player_id=player.id, exclusive=True,
                start_date=today, end_date=end,
            )
            per_agent[agent.id] += 1

        print(f"TransferX players: {len(players)}; already represented: {len(players) - len(todo)}; "
              f"allocated now: {len(todo)}, mandates to {end.isoformat()}")
        for agent in agents:
            print(f"  {agent.display_name} ({agent.agency_name}): {per_agent[agent.id]} players")

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
