#!/usr/bin/env python
"""
Backfill player history from API-Football for the player profile ledger
(docs/feature_spec/player-profile-ledger, P1).

For TransferX players only (CONTRACTED at a club on TransferX, or a
FREE_AGENT; product owner, 2026-10-01), in stages:

  seasons     Season stats by competition and club, for the current season
              and the `--seasons` before it (/players?id=&season=)
  transfers   Transfer history (/transfers?player=)
  sidelined   Injury periods (/sidelined?player=)
  loans       Mark season rows played on loan (no API calls)
  injuries    Matches missed, per competition-season he played in
              (/injuries?league=&season=), for games missed and availability
  fixtures    Matches each of his clubs played per competition-season
              (/teams/statistics), for availability
  recent      His club's last 5 matches and his rating in each
              (/fixtures?team=&last=5, /fixtures/players?fixture=)

Every item fetched is recorded in `vendor_fetch_log`, so a stopped run
resumes where it left off and a re-run makes no repeat calls (`--refresh`
re-fetches). The current season is the latest one in player_stats, unless
`--current-season` says otherwise (API-Football counts a season by its
first year: 2025 is 2025/26).

Usage (inside Docker, or a shell on the Railway API service):
    python scripts/backfill_player_history.py --dry-run
    python scripts/backfill_player_history.py
    python scripts/backfill_player_history.py --stages recent --refresh   # weekly
Options: --seasons 3, --limit N (players), --per-minute 300, --max-calls 30000.
"""

import argparse
import asyncio
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import backfill_demo_squad_contracts  # noqa: F401,E402  (registers every model)
from app.config import settings  # noqa: E402
from app.players.models import Player, PlayerStatus  # noqa: E402
from app.stats.models import PlayerStats  # noqa: E402
from app.vendor import history  # noqa: E402
from app.vendor.client import ApiFootballClient, ApiFootballError  # noqa: E402

STAGES = ("seasons", "transfers", "sidelined", "loans", "injuries", "fixtures", "recent")


class Budget(Exception):
    """The run's call budget is spent; stop cleanly and resume next time."""


class ThrottledClient(ApiFootballClient):
    """At most `per_minute` calls a minute and `max_calls` in the run.
    API-Football answers some errors (a plan limit, a bad parameter) with
    200 and an `errors` field; those are raised, not stored as empty."""

    def __init__(self, key: str, base_url: str, per_minute: int, max_calls: int):
        super().__init__(key, base_url)
        self.gap = 60.0 / per_minute
        self.max_calls = max_calls
        self.calls = 0
        self.last = 0.0
        self.by_path: Counter = Counter()

    async def _get(self, path: str, params: dict | None = None) -> dict:
        if self.calls >= self.max_calls:
            raise Budget()
        wait = self.last + self.gap - time.monotonic()
        if wait > 0:
            await asyncio.sleep(wait)
        self.last = time.monotonic()
        self.calls += 1
        self.by_path[path] += 1
        data = await super()._get(path, params)
        errors = data.get("errors")
        if errors and (not isinstance(errors, list) or len(errors) > 0):
            raise ApiFootballError(f"{path} {params}: {errors}")
        return data


async def main(args) -> None:
    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    stages = args.stages.split(",") if args.stages else list(STAGES)
    unknown = [s for s in stages if s not in STAGES]
    if unknown:
        sys.exit(f"Unknown stage(s): {', '.join(unknown)}. Stages: {', '.join(STAGES)}")
    if not settings.apisports_key and not args.dry_run:
        sys.exit("APISPORTS_KEY is not set")
    client = ThrottledClient(settings.apisports_key or "", settings.api_football_base_url,
                             args.per_minute, args.max_calls)

    async with session_factory() as db:
        current = args.current_season or int(
            (await db.execute(select(func.max(PlayerStats.season)))).scalar() or 2025)
        seasons = [current - i for i in range(args.seasons + 1)]
        players = (await db.execute(
            select(Player).where(Player.status.in_([PlayerStatus.CONTRACTED, PlayerStatus.FREE_AGENT]),
                                 Player.vendor_id.isnot(None))
            .order_by(Player.name, Player.id)
        )).scalars().all()
        if args.limit:
            players = players[: args.limit]
        by_vendor = {str(p.vendor_id): p.id for p in players}
        ids = [p.id for p in players]
        print(f"{len(players)} TransferX players · seasons {', '.join(f'{s}/{(s + 1) % 100:02d}' for s in seasons)}"
              f" · stages {', '.join(stages)}{' · DRY RUN' if args.dry_run else ''}")

        planned: Counter = Counter()
        done: Counter = Counter()
        failed: Counter = Counter()

        async def step(stage: str, key: str, fetch):
            """Run one fetch unless it's logged as done; log and commit it."""
            if not args.refresh and await history.already_fetched(db, key):
                return
            planned[stage] += 1
            if args.dry_run:
                return
            try:
                results = await fetch()
            except Budget:
                raise
            except Exception as exc:  # one bad item never stops the run; it isn't logged, so it's retried next time
                await db.rollback()
                failed[stage] += 1
                print(f"  ! {stage} {key}: {type(exc).__name__}: {str(exc)[:160]}")
                return
            await history.mark_fetched(db, key, results if isinstance(results, int) else None)
            await db.commit()
            done[stage] += 1
            if sum(done.values()) % 100 == 0:
                print(f"  … {sum(done.values())} done, {client.calls} calls")

        try:
            if "seasons" in stages:
                for p in players:
                    for s in seasons:
                        await step("seasons", f"player-season:{p.id}:{s}",
                                   lambda p=p, s=s: history.sync_player_season(db, p, s, client))
            if "transfers" in stages:
                for p in players:
                    await step("transfers", f"transfers:{p.id}", lambda p=p: history.refresh_transfers(db, p, client))
            if "sidelined" in stages:
                for p in players:
                    await step("sidelined", f"sidelined:{p.id}", lambda p=p: history.refresh_sidelined(db, p, client))
            if "loans" in stages and not args.dry_run:
                flagged = 0
                for p in players:
                    flagged += await history.mark_loan_seasons(db, p.id)
                await db.commit()
                print(f"  loans: {flagged} season rows marked as loan spells")

            # The competitions and clubs his seasons were played in.
            spells = (await db.execute(
                select(PlayerStats.league_id, PlayerStats.season, PlayerStats.team_vendor_id)
                .where(PlayerStats.player_id.in_(ids), PlayerStats.season.in_([str(s) for s in seasons]),
                       PlayerStats.appearances > 0)
                .distinct()
            )).all() if ids else []
            # Older rows can hold the text "None" for a missing league or club.
            spells = [(lg, s, t) for lg, s, t in spells if lg not in (None, "", "None") and t not in ("", "None")]
            if "injuries" in stages:
                for league_id, season in sorted({(lg, s) for lg, s, _ in spells if lg and s}):
                    await step("injuries", f"league-injuries:{league_id}:{season}",
                               lambda lg=league_id, s=season: history.sync_league_injuries(
                                   db, lg, int(s), client, by_vendor))
            if "fixtures" in stages:
                for league_id, season, team in sorted({sp for sp in spells if all(sp)}):
                    await step("fixtures", f"team-fixtures:{team}:{league_id}:{season}",
                               lambda t=team, lg=league_id, s=season: history.sync_team_fixture_count(
                                   db, t, lg, int(s), client))
            if "recent" in stages:
                teams = sorted({t for lg, s, t in spells if s == str(current) and t})
                for team in teams:
                    async def recent(team=team):
                        _, stored = await history.sync_team_recent_ratings(db, team, client, by_vendor)
                        return stored
                    await step("recent", f"team-recent:{team}:{time.strftime('%Y-%W')}", recent)
        except Budget:
            print(f"Call budget of {args.max_calls} reached; run again to continue.")

    if args.dry_run:
        print("Calls needed:", dict(planned), f"(about {sum(planned.values()) + planned['recent'] * 5} with the per-match calls)")
    else:
        print("Done:", dict(done), f"· {client.calls} API calls", dict(client.by_path))
        if failed:
            print("Failed (will retry on the next run):", dict(failed))
    await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--stages", help=f"comma-separated, of: {', '.join(STAGES)} (default: all)")
    parser.add_argument("--seasons", type=int, default=3, help="past seasons as well as the current one")
    parser.add_argument("--current-season", type=int, help="API-Football's starting year of the current season")
    parser.add_argument("--limit", type=int, help="only the first N players")
    parser.add_argument("--per-minute", type=int, default=300)
    parser.add_argument("--max-calls", type=int, default=30000)
    parser.add_argument("--refresh", action="store_true", help="re-fetch items already fetched")
    asyncio.run(main(parser.parse_args()))
