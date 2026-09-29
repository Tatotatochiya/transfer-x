#!/usr/bin/env python
"""
Development / demo: make every Premier League club a TransferX club.

Only Arsenal, Chelsea and Liverpool were on TransferX; the other 17 clubs of
the 2025/26 Premier League existed only as vendor-imported world teams, their
players EXTERNAL (visible, not signable). For each of those 17 this creates,
through the same service functions the app uses:

- the club's owner account, `<name>@transferx.com` (the full club name,
  lower-case, joined: astonvilla, manchestercity, …), signing in with that
  username or email and the shared demo password;
- the club (name, country and crest from the world team, league "Premier
  League") and its finance: a tiered transfer budget (the biggest clubs about
  £200–250m, promoted clubs £55–70m) and a weekly wage budget about 30% above
  the squad's wage bill;
- an active contract for every player at the world team (players.service.
  create_contract, which re-derives each player as CONTRACTED at the club),
  with a wage from the fee model where there is one and an end date on the
  same 30 June / 31 January spread as mock_contract_end_dates.py. The wages
  are the club's running wage bill (wage_reserved_weekly), as
  backfill_contract_wages.py does for the original three.

It also relabels the three original clubs' league as "Premier League": their
`league_name` held "UEFA Champions League", the last competition the vendor
synced, not their league.

Idempotent: a club already on TransferX (by name) is skipped, so a second run
does nothing. One transaction; --dry-run rolls it back.

Usage (inside Docker):
    docker compose exec api python scripts/onboard_premier_league_clubs.py --dry-run
    docker compose exec api python scripts/onboard_premier_league_clubs.py
    (--password to choose the shared password; default password123, as the
    existing demo clubs)
"""

import argparse
import asyncio
import random
import re
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

# Registers every model module, and gives the wage model the original
# squads were given (fair value x 0.004/week, a flat range otherwise).
from backfill_demo_squad_contracts import _generate_terms  # noqa: E402
from mock_contract_end_dates import mock_end_date  # noqa: E402

from app.auth import service as auth_service  # noqa: E402
from app.auth.models import UserType  # noqa: E402
from app.clubs import service as clubs_service  # noqa: E402
from app.clubs.models import Club  # noqa: E402
from app.config import settings  # noqa: E402
from app.players import service as players_service  # noqa: E402
from app.players.models import Player  # noqa: E402
from app.valuation import service as valuation_service  # noqa: E402
from app.world.models import WorldTeam  # noqa: E402

PREMIER_LEAGUE = "Premier League"
ORIGINAL_CLUBS = ("Arsenal", "Chelsea", "Liverpool")
# The 2025/26 clubs not yet on TransferX, with a transfer budget (£m) tiered
# by stature; promoted clubs (Leeds, Burnley, Sunderland) lowest. Newcastle's
# world team is labelled with a European competition, so it is named here
# rather than found by league.
NEW_CLUBS: dict[str, int] = {
    "Manchester City": 250, "Manchester United": 220, "Newcastle": 200, "Tottenham": 180,
    "Aston Villa": 150, "Brighton": 120, "Nottingham Forest": 110, "West Ham": 110,
    "Crystal Palace": 100, "Everton": 100, "Bournemouth": 90, "Brentford": 90,
    "Fulham": 85, "Wolves": 80, "Leeds": 70, "Sunderland": 60, "Burnley": 55,
}
SEED = 2026


def username_for(club_name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", club_name.lower())


async def main(dry_run: bool, password: str) -> None:
    random.seed(SEED)
    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    today = date.today()

    async with session_factory() as db:
        existing = {
            n.lower() for n in (await db.execute(select(Club.name))).scalars()
        }
        created = 0
        for name, budget_m in NEW_CLUBS.items():
            if name.lower() in existing:
                print(f"  {name}: already on TransferX — skipped")
                continue
            team = (await db.execute(
                select(WorldTeam).where(func.lower(WorldTeam.name) == name.lower()).order_by(WorldTeam.season.desc())
            )).scalars().first()
            if team is None:
                print(f"  {name}: no world team found — skipped")
                continue

            email = f"{username_for(name)}@transferx.com"
            user = await auth_service.create_user(db, email=email, password=password, user_type=UserType.CLUB)
            club = await clubs_service.create_club(db, user_id=user.id, name=name)
            club.country = team.country
            club.crest_url = team.crest_url
            club.league_name = PREMIER_LEAGUE
            finance = await clubs_service.create_club_finance(db, club.id)

            squad = (await db.execute(
                select(Player).where(Player.world_team_id == team.id, Player.current_club_id.is_(None))
            )).scalars().all()
            valuations = await valuation_service.get_latest_valuations(db, [p.id for p in squad])
            wage_bill = Decimal("0")
            for player in squad:
                valuation = valuations.get(player.id)
                _, _, wage = _generate_terms(valuation.fair_value if valuation else None)
                end = mock_end_date(player.id, today)
                start = date(end.year - random.choice([2, 3, 3, 4, 5]), 7, 1)
                await players_service.create_contract(
                    db, player, club_id=club.id, start_date=start, end_date=end, wage_weekly=wage,
                )
                player.contract_expiry = end
                wage_bill += wage

            finance.transfer_budget_total = Decimal(budget_m) * 1_000_000
            finance.wage_reserved_weekly = wage_bill
            finance.wage_budget_total_weekly = (wage_bill * Decimal("1.3")).quantize(Decimal("1000"))
            created += 1
            print(f"  {name}: {email} — {len(squad)} players, £{budget_m}m transfer, "
                  f"£{wage_bill:,.0f}/wk wage bill")

        relabelled = 0
        for club in (await db.execute(select(Club).where(Club.name.in_(ORIGINAL_CLUBS)))).scalars():
            if club.league_name != PREMIER_LEAGUE:
                club.league_name = PREMIER_LEAGUE
                relabelled += 1
        print(f"Clubs created: {created}; original clubs relabelled to {PREMIER_LEAGUE}: {relabelled}")

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
    parser.add_argument("--password", default="password123")
    args = parser.parse_args()
    asyncio.run(main(args.dry_run, args.password))
