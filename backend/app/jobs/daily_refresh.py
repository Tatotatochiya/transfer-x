"""The scheduled data refresh (docs/feature_spec/scheduled-data-refresh.md).

Runs in the `stats-worker` Railway cron service at 17:00 and 22:00 UK time:

    python -m app.jobs.daily_refresh            # exits unless it's 17:00 or 22:00 in London
    python -m app.jobs.daily_refresh --force    # run now
    python -m app.jobs.daily_refresh --force --steps stats,form

Railway's cron is UTC, so it fires at 16, 17, 21 and 22 UTC and this exits
straight away unless it's actually 17:00 or 22:00 in London — two runs a day
through the clock changes.

Steps, each isolated (one league failing doesn't stop the others):
  stats       current-season player stats for every league in world_leagues
  injuries    current-season injuries for each league
  form        ratings for matches finished since the last run, fixture counts
              for the clubs that played, then form scores
  valuations  the daily model recompute (22:00 run only)

Then one Slack message for the run. The web app's Admin → Jobs page starts
the same refresh as a manual run (`run_refresh(trigger="manual")`).
"""
import argparse
import asyncio
import logging
import sys
import time
import uuid
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select, text

from app import monitoring
from app.common import slack
from app.config import settings
from app.monitoring.models import JobRun
from app.monitoring.runs import finish_run, is_running, record_run, start_run
from app.vendor.client import ApiFootballClient, ApiFootballError

logger = logging.getLogger("app.jobs.daily_refresh")

JOB = "daily_refresh"
LONDON = ZoneInfo("Europe/London")
SLOTS = (17, 22)           # UK hours the refresh runs at
VALUATION_SLOT = 22        # the daily valuation recompute follows this run
ALL_STEPS = ("stats", "injuries", "form", "valuations")
PER_MINUTE = 250           # Pro allows 300 a minute; stay under it
LOCK_KEY = 704_221_001     # pg advisory lock: one refresh at a time
FINISHED = "FT-AET-PEN"    # /fixtures statuses for a finished match
TRANSIENT_RETRIES = 2      # API-Football's own "bug" errors usually pass
TRANSIENT_WAIT = 3.0       # seconds, times the attempt


class OutOfQuota(Exception):
    """The day's remaining API-Football requests reached the reserve."""


class QuotaClient(ApiFootballClient):
    """Counts calls, keeps under the per-minute limit, and stops before the
    day's remaining requests fall to the reserve. API-Football answers some
    errors with 200 and an `errors` field; those are raised."""

    def __init__(self, key: str, base_url: str, reserve: int, per_minute: int = PER_MINUTE):
        super().__init__(key, base_url)
        self.reserve = reserve
        self.gap = 60.0 / per_minute
        self.calls = 0
        self.remaining: int | None = None
        self._last = 0.0

    async def _get(self, path: str, params: dict | None = None) -> dict:
        for attempt in range(TRANSIENT_RETRIES + 1):
            if self.remaining is not None and self.remaining <= self.reserve:
                raise OutOfQuota()
            wait = self._last + self.gap - time.monotonic()
            if wait > 0:
                await asyncio.sleep(wait)
            self._last = time.monotonic()
            self.calls += 1
            data = await super()._get(path, params)
            left = self.last_headers.get("x-ratelimit-requests-remaining")
            if left is not None and str(left).isdigit():
                self.remaining = int(left)
            errors = data.get("errors")
            if not errors or (isinstance(errors, list) and len(errors) == 0):
                return data
            # "This is on our side" ({"bug": …}) passes; anything else is ours.
            if isinstance(errors, dict) and "bug" in errors and attempt < TRANSIENT_RETRIES:
                await asyncio.sleep(TRANSIENT_WAIT * (attempt + 1))
                continue
            raise ApiFootballError(f"{path}: {errors}")
        raise ApiFootballError(f"{path}: gave up")


def uk_slot(now: datetime | None = None) -> int | None:
    """17 or 22 when it's within half an hour after that UK hour, else None."""
    local = (now or datetime.now(timezone.utc)).astimezone(LONDON)
    return local.hour if local.hour in SLOTS and local.minute < 30 else None


def steps_for(slot: int | None, requested: list[str] | None) -> list[str]:
    if requested:
        return [s for s in ALL_STEPS if s in requested]
    return [s for s in ALL_STEPS if s != "valuations" or slot == VALUATION_SLOT]


# ── Steps ────────────────────────────────────────────────────────────────────


async def _leagues(db) -> list[tuple[str, int, str]]:
    """(league id, season, name) for every league TransferX syncs."""
    from app.world.models import WorldLeague

    rows = (await db.execute(select(WorldLeague))).scalars().all()
    out = []
    for lg in rows:
        if str(lg.league_id).isdigit() and str(lg.season or "").isdigit():
            out.append((str(lg.league_id), int(lg.season), lg.name or f"League {lg.league_id}"))
    return sorted(out, key=lambda t: int(t[0]))


async def update_seasons(db, client, summary: dict) -> None:
    """Move each league to API-Football's current season (/leagues?current),
    so the refresh follows a new season without anyone changing it by hand."""
    from app.world.models import WorldLeague

    for lg in (await db.execute(select(WorldLeague))).scalars().all():
        if not str(lg.league_id).isdigit():
            continue
        try:
            resp = await client._get("/leagues", {"id": int(lg.league_id), "current": "true"})
        except OutOfQuota:
            raise
        except Exception as exc:  # noqa: BLE001 — keep the season it has
            logger.warning("Couldn't check the current season of %s: %s", lg.name, exc)
            continue
        current = next((str(se["year"]) for item in resp.get("response") or []
                        for se in item.get("seasons") or [] if se.get("current") and se.get("year")), None)
        if current and current != str(lg.season):
            logger.info("Season · %s moved from %s to %s", lg.name, lg.season, current)
            summary.setdefault("seasons_moved", []).append(f"{lg.name} {lg.season}→{current}")
            lg.season = current
    await db.commit()


async def _players_by_vendor(db) -> dict[str, uuid.UUID]:
    from app.players.models import Player

    rows = (await db.execute(select(Player.vendor_id, Player.id).where(Player.vendor_id.isnot(None)))).all()
    return {str(v): pid for v, pid in rows}


async def _since(db) -> date:
    """Fetch matches from the day before the last refresh that got through,
    at most a week back (three days on the first run)."""
    last = (await db.execute(select(JobRun.started_at).where(
        JobRun.job == JOB, JobRun.status.in_(["succeeded", "partial"]),
    ).order_by(JobRun.started_at.desc()).limit(1))).scalar()
    today = datetime.now(timezone.utc).date()
    if last is None:
        return today - timedelta(days=3)
    return max(last.date() - timedelta(days=1), today - timedelta(days=7))


async def step_stats(db, client, leagues, summary: dict, failures: list) -> None:
    from app.vendor.sync import sync_league

    for league_id, season, name in leagues:
        try:
            res = await sync_league(db, int(league_id), season, client)
            await db.commit()
        except OutOfQuota:
            await db.rollback()
            raise
        except Exception as exc:  # noqa: BLE001
            await db.rollback()
            failures.append(f"stats · {name}: {type(exc).__name__}")
            logger.warning("Stats for %s failed: %s", name, exc)
            continue
        summary["players_updated"] = summary.get("players_updated", 0) + res["players_updated"]
        summary["players_created"] = summary.get("players_created", 0) + res["players_created"]
        summary["snapshots"] = summary.get("snapshots", 0) + res["snapshots_created"]
        logger.info("Stats · %s: %s players updated, %s new, %s pages",
                    name, res["players_updated"], res["players_created"], res["pages_synced"])


async def step_injuries(db, client, leagues, summary: dict, failures: list) -> None:
    from app.vendor.history import sync_league_injuries

    by_vendor = await _players_by_vendor(db)
    for league_id, season, name in leagues:
        try:
            stored = await sync_league_injuries(db, league_id, season, client, by_vendor)
            await db.commit()
        except OutOfQuota:
            await db.rollback()
            raise
        except Exception as exc:  # noqa: BLE001
            await db.rollback()
            failures.append(f"injuries · {name}: {type(exc).__name__}")
            logger.warning("Injuries for %s failed: %s", name, exc)
            continue
        summary["injuries_new"] = summary.get("injuries_new", 0) + stored
        logger.info("Injuries · %s: %s new matches missed", name, stored)


async def step_form(db, client, leagues, summary: dict, failures: list) -> None:
    from app.stats.models import PlayerFixtureRating
    from app.vendor.history import store_fixture_ratings, sync_team_fixture_count
    from app.vendor.sync import compute_all_form

    by_vendor = await _players_by_vendor(db)
    since = await _since(db)
    today = datetime.now(timezone.utc).date()
    played: set[tuple[str, str, int]] = set()  # (team, league, season)
    for league_id, season, name in leagues:
        try:
            fixtures = (await client._get("/fixtures", {
                "league": int(league_id), "season": season, "from": since.isoformat(),
                "to": today.isoformat(), "status": FINISHED,
            })).get("response") or []
            new = 0
            for f in fixtures:
                fid = str((f.get("fixture") or {}).get("id") or "")
                if not fid:
                    continue
                for side in ("home", "away"):
                    team = ((f.get("teams") or {}).get(side) or {}).get("id")
                    if team:
                        played.add((str(team), league_id, season))
                if (await db.execute(select(PlayerFixtureRating.id).where(
                        PlayerFixtureRating.fixture_vendor_id == fid).limit(1))).first():
                    continue
                summary["ratings"] = summary.get("ratings", 0) + await store_fixture_ratings(db, f, client, by_vendor)
                new += 1
            await db.commit()
        except OutOfQuota:
            await db.rollback()
            raise
        except Exception as exc:  # noqa: BLE001
            await db.rollback()
            failures.append(f"form · {name}: {type(exc).__name__}")
            logger.warning("Recent matches for %s failed: %s", name, exc)
            continue
        summary["matches_new"] = summary.get("matches_new", 0) + new
        logger.info("Matches · %s: %s finished since %s, %s new", name, len(fixtures), since, new)

    for team, league_id, season in sorted(played):
        try:
            await sync_team_fixture_count(db, team, league_id, season, client)
            await db.commit()
            summary["fixture_counts"] = summary.get("fixture_counts", 0) + 1
        except OutOfQuota:
            await db.rollback()
            raise
        except Exception as exc:  # noqa: BLE001
            await db.rollback()
            failures.append(f"form · team {team}: {type(exc).__name__}")
    summary["form_updated"] = await compute_all_form(db)
    await db.commit()
    logger.info("Form · %s players updated", summary["form_updated"])


async def step_valuations(db, client, leagues, summary: dict, failures: list) -> None:
    from app.valuation.service import compute_all_valuations

    counts = await compute_all_valuations(db)
    await db.commit()
    summary["valuations"] = counts["updated"]
    summary["valuations_skipped"] = counts["skipped_ineligible"]
    if counts["errors"]:
        failures.append(f"valuations: {counts['errors']} players failed")
    logger.info("Valuations · %s updated, %s not eligible, %s errors",
                counts["updated"], counts["skipped_ineligible"], counts["errors"])


STEP_FUNCS = {"stats": step_stats, "injuries": step_injuries, "form": step_form, "valuations": step_valuations}
API_STEPS = {"stats", "injuries", "form"}


# ── The run ──────────────────────────────────────────────────────────────────


async def _try_lock(db) -> bool:
    if db.bind.dialect.name != "postgresql":
        return True
    return bool((await db.execute(text("SELECT pg_try_advisory_lock(:k)"), {"k": LOCK_KEY})).scalar())


async def _unlock(db) -> None:
    if db.bind.dialect.name == "postgresql":
        await db.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": LOCK_KEY})


def _fmt_duration(ms: int) -> str:
    s = ms // 1000
    return f"{s // 60}m {s % 60:02d}s" if s >= 60 else f"{s}s"


def slack_text(status: str, slot: int | None, summary: dict, duration_ms: int, error: str | None) -> str:
    icon = {"succeeded": "✅", "partial": "⚠️", "failed": "❌"}.get(status, "ℹ️")
    when = f"{slot}:00" if slot else "manual"
    parts = [f"{icon} *Data refresh, {when}* · {_fmt_duration(duration_ms)}"]
    bits = []
    labels = [("leagues", "leagues"), ("players_updated", "players updated"), ("injuries_new", "new injuries"),
              ("matches_new", "new matches"), ("form_updated", "form scores"), ("valuations", "valuations")]
    for key, label in labels:
        if key in summary:
            bits.append(f"{summary[key]:,} {label}")
    if "api_calls" in summary:
        left = summary.get("api_remaining")
        bits.append(f"API calls {summary['api_calls']:,}" + (f" ({left:,} left today)" if left is not None else ""))
    if bits:
        parts.append(" · ".join(bits))
    if status != "succeeded":
        problems = list(summary.get("failures") or [])
        if error:
            problems.insert(0, error[:200])
        if summary.get("stopped"):
            problems.insert(0, summary["stopped"])
        if problems:
            parts.append("Not done: " + "; ".join(problems[:5]))
        parts.append(f"<{slack.admin_link('/admin/jobs')}|Admin → Jobs>")
    return "\n".join(parts)


async def run_refresh(*, trigger: str, steps: list[str], slot: int | None = None,
                      user_id: uuid.UUID | None = None, client: ApiFootballClient | None = None) -> dict:
    """Run the refresh once. Returns {"status", "run_id"}; never raises."""
    if await is_running(JOB):
        async with monitoring.sessions()() as db:
            db.add(JobRun(id=uuid.uuid4(), job=JOB, trigger=trigger, service=monitoring.service,
                          triggered_by_user_id=user_id, status="skipped", started_at=datetime.now(timezone.utc),
                          finished_at=datetime.now(timezone.utc), duration_ms=0,
                          error="Another refresh is already running"))
            await db.commit()
        logger.info("Refresh skipped: another is already running")
        return {"status": "skipped", "run_id": None}

    if client is None and any(s in API_STEPS for s in steps):
        if not settings.apisports_key:
            steps = [s for s in steps if s not in API_STEPS]
            logger.warning("APISPORTS_KEY is not set: skipping the API-Football steps")
        else:
            client = QuotaClient(settings.apisports_key, settings.api_football_base_url, settings.apisports_reserve)

    started = time.monotonic()
    status, run_id, summary, error = "failed", None, {}, None
    try:
        async with record_run(JOB, trigger=trigger, user_id=user_id) as run:
            run_id = run.id
            summary = run.summary
            summary["steps"] = steps
            if slot:
                summary["slot"] = slot
            failures: list[str] = []
            async with monitoring.sessions()() as db:
                if not await _try_lock(db):
                    run.status, run.error = "skipped", "Another refresh holds the lock"
                    return {"status": "skipped", "run_id": run.id}
                try:
                    if client is not None and any(s in API_STEPS for s in steps):
                        try:
                            await update_seasons(db, client, summary)
                        except OutOfQuota:
                            summary["stopped"] = "Stopped before starting: API-Football quota reserve reached"
                            steps = []
                    leagues = await _leagues(db)
                    summary["leagues"] = len(leagues)
                    logger.info("Refresh started: %s, %s leagues", ", ".join(steps), len(leagues))
                    for step in steps:
                        child = await start_run(f"{JOB}.{step}", trigger=trigger, parent_id=run.id, user_id=user_id)
                        t0, before = time.monotonic(), len(failures)
                        snapshot = dict(summary)
                        try:
                            await STEP_FUNCS[step](db, client, leagues, summary, failures)
                        except OutOfQuota:
                            summary["stopped"] = f"Stopped at {step}: API-Football quota reserve reached"
                            await finish_run(child.id, status="partial", started=t0, summary=None,
                                             error=summary["stopped"])
                            logger.warning(summary["stopped"])
                            break
                        except Exception as exc:  # noqa: BLE001
                            await db.rollback()
                            failures.append(f"{step}: {type(exc).__name__}: {str(exc)[:120]}")
                            logger.exception("Step %s failed", step)
                            await finish_run(child.id, status="failed", started=t0, summary=None,
                                             error=f"{type(exc).__name__}: {exc}")
                            continue
                        # What this step added: counts are cumulative across the run.
                        changed = {k: (v - snapshot.get(k, 0) if isinstance(v, int) else v)
                                   for k, v in summary.items() if snapshot.get(k) != v}
                        await finish_run(child.id, status="partial" if len(failures) > before else "succeeded",
                                         started=t0, summary=changed, error="; ".join(failures[before:])[:2000] or None)
                finally:
                    await _unlock(db)
                    await db.commit()
            if client is not None and hasattr(client, "calls"):
                summary["api_calls"] = client.calls
                summary["api_remaining"] = client.remaining
            if failures:
                summary["failures"] = failures[:20]
            done_any = any(k in summary for k in ("players_updated", "injuries_new", "form_updated", "valuations"))
            if summary.get("stopped") or failures:
                run.status = "partial" if done_any else "failed"
                run.error = summary.get("stopped") or "; ".join(failures)[:2000]
            status = run.status or "succeeded"
            error = run.error
            logger.info("Refresh %s", status)
    except Exception as exc:  # noqa: BLE001 — recorded as failed by record_run
        status, error = "failed", f"{type(exc).__name__}: {exc}"
        logger.exception("Refresh failed")
    if status != "skipped":
        await slack.post(slack_text(status, slot, summary, int((time.monotonic() - started) * 1000), error))
    return {"status": status, "run_id": run_id}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--force", action="store_true", help="run whatever the time")
    parser.add_argument("--steps", help=f"comma-separated, from {', '.join(ALL_STEPS)}")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    monitoring.service = "worker"
    slot = uk_slot()
    if slot is None and not args.force:
        logger.info("Not a refresh time in the UK (runs at %s); exiting",
                    " and ".join(f"{h}:00" for h in SLOTS))
        return 0
    requested = [s.strip() for s in args.steps.split(",")] if args.steps else None
    if requested and (bad := [s for s in requested if s not in ALL_STEPS]):
        parser.error(f"unknown step(s): {', '.join(bad)}")

    import app.main  # noqa: F401 — registers every model
    from app.monitoring import errors
    from app.monitoring.runs import install_log_capture

    install_log_capture()

    async def go() -> dict:
        errors.install()
        writer = asyncio.create_task(errors.writer_loop())
        try:
            return await run_refresh(trigger="cron" if not args.force else "manual",
                                     steps=steps_for(slot, requested), slot=slot)
        finally:
            await errors.drain()
            writer.cancel()
            from app.database import engine

            await engine.dispose()

    result = asyncio.run(go())
    return 0 if result["status"] in ("succeeded", "partial", "skipped") else 1


if __name__ == "__main__":
    sys.exit(main())
