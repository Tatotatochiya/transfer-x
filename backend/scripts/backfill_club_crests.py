#!/usr/bin/env python
"""
Development / demo: give TransferX clubs with no crest the crest of their
API-Football team.

The clubs created by onboard_premier_league_clubs.py took their crest from
the vendor's world team; the clubs that existed before it (Arsenal, Chelsea,
Liverpool on Railway) never had one, so every page that shows a crest fell
back to an initial ("A", "L"). This copies the crest from the world team of
the same name (ignoring case; the latest season when the vendor has several).

Only clubs with no crest are touched, so a second run does nothing, and a
crest someone set by hand is never replaced. A club with no world team of
its name is listed and left alone. One transaction; --dry-run rolls it back.

Usage (inside Docker, or a shell on the Railway API service):
    python scripts/backfill_club_crests.py --dry-run
    python scripts/backfill_club_crests.py
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import backfill_demo_squad_contracts  # noqa: F401,E402  (registers every model)
from app.clubs.models import Club  # noqa: E402
from app.config import settings  # noqa: E402
from app.world.models import WorldTeam  # noqa: E402


async def main(dry_run: bool) -> None:
    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as db:
        clubs = (await db.execute(
            select(Club).where((Club.crest_url.is_(None)) | (Club.crest_url == "")).order_by(Club.name)
        )).scalars().all()
        filled = 0
        for club in clubs:
            team = (await db.execute(
                select(WorldTeam).where(func.lower(WorldTeam.name) == club.name.lower(), WorldTeam.crest_url.isnot(None))
                .order_by(WorldTeam.season.desc().nulls_last())
            )).scalars().first()
            if team is None:
                print(f"  {club.name}: no API-Football team of that name — left without a crest")
                continue
            club.crest_url = team.crest_url
            filled += 1
            print(f"  {club.name}: {team.crest_url}")
        print(f"Clubs without a crest: {len(clubs)}; filled: {filled}")
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
