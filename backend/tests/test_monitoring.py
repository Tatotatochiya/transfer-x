"""Scheduled data refresh, job runs, error tracking and request health
(docs/feature_spec/scheduled-data-refresh.md)."""
import ast
import logging
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import func, select

from app.common import slack
from app.config import settings
from app.jobs import daily_refresh as dr
from app.monitoring import errors, requests as reqs, retention, runs, watch
from app.monitoring.models import ErrorEvent, ErrorIssue, JobRun, JobRunLog, RequestMinute
from app.vendor.client import ApiFootballClient
from tests.conftest import _auth_headers, _register


@pytest_asyncio.fixture(autouse=True)
async def monitoring_db(db_engine, monkeypatch):
    """Monitoring writes in its own sessions: point them at the test engine,
    and catch Slack posts instead of sending them."""
    errors.reset()
    reqs.reset()
    slack.reset_limits()
    watch._alerted.clear()
    sent: list[str] = []

    async def fake_post(text, *, key=None, every_seconds=0):
        sent.append(text)
        return True

    monkeypatch.setattr(slack, "post", fake_post)
    yield sent


@pytest_asyncio.fixture
async def admin(client: AsyncClient, db) -> dict:
    from app.auth.models import User

    tokens = await _register(client, "monadmin@test.com", club_name="Monitor FC")
    (await db.execute(select(User).where(User.email == "monadmin@test.com"))).scalar_one().is_superuser = True
    await db.commit()
    return tokens


# ── Run recorder ─────────────────────────────────────────────────────────────


async def test_record_run_keeps_status_summary_and_log_lines(db):
    runs.install_log_capture()
    log = logging.getLogger("app.test.job")
    async with runs.record_run("test_job", trigger="manual") as run:
        row = await db.get(JobRun, run.id)
        assert row.status == "running"
        log.info("did %s things", 3)
        run.summary["things"] = 3
    db.expire_all()
    row = await db.get(JobRun, run.id)
    assert row.status == "succeeded" and row.summary == {"things": 3} and row.duration_ms is not None
    lines = (await db.execute(select(JobRunLog).where(JobRunLog.run_id == run.id))).scalars().all()
    assert [line.message for line in lines] == ["did 3 things"]


async def test_record_run_marks_failure_and_reraises(db):
    with pytest.raises(ValueError):
        async with runs.record_run("test_job", trigger="cron") as run:
            raise ValueError("boom")
    db.expire_all()
    row = await db.get(JobRun, run.id)
    assert row.status == "failed" and "boom" in row.error


async def test_a_run_left_running_shows_as_lost():
    row = JobRun(job="x", trigger="cron", service="worker", status="running",
                 started_at=datetime.now(timezone.utc) - timedelta(hours=3))
    assert runs.shown_status(row) == "lost"


# ── UK time slots ────────────────────────────────────────────────────────────


@pytest.mark.parametrize("utc, slot", [
    ("2026-07-01T16:05:00", 17),   # BST: 17:05 in London
    ("2026-07-01T21:10:00", 22),
    ("2026-07-01T17:05:00", None),  # 18:05 in London
    ("2026-12-01T17:05:00", 17),   # GMT
    ("2026-12-01T16:05:00", None),
    ("2026-12-01T22:40:00", None),  # past the half hour
])
def test_uk_slot_follows_the_clock_change(utc, slot):
    assert dr.uk_slot(datetime.fromisoformat(utc).replace(tzinfo=timezone.utc)) == slot


def test_valuations_only_after_the_22_run():
    assert dr.steps_for(17, None) == ["stats", "injuries", "form"]
    assert dr.steps_for(22, None) == ["stats", "injuries", "form", "valuations"]
    assert dr.steps_for(None, ["valuations", "stats"]) == ["stats", "valuations"]


# ── The refresh ──────────────────────────────────────────────────────────────


def _api_player(vid: int, minutes: int) -> dict:
    return {
        "player": {"id": vid, "name": f"P. Player{vid}", "firstname": "P", "lastname": f"Player{vid}", "age": 24,
                   "nationality": "England", "photo": None, "birth": {}},
        "statistics": [{
            "team": {"id": 42, "name": "Arsenal"}, "league": {"id": 39, "name": "Premier League", "season": 2025},
            "games": {"appearences": 10, "minutes": minutes, "position": "Attacker", "rating": "7.1"},
            "goals": {"total": 3, "assists": 1}, "shots": {}, "passes": {}, "tackles": {}, "duels": {},
            "dribbles": {}, "fouls": {}, "cards": {}, "penalty": {}, "substitutes": {},
        }],
    }


class FakeApi:
    """Canned API-Football answers, and the quota header."""

    def __init__(self, remaining: list[int] | None = None, minutes: int = 900, season: int | None = None):
        self.season = season
        self.calls: list[str] = []
        self.remaining = remaining or []
        self.minutes = minutes

    async def get(self, client, path, params=None):
        self.calls.append(path)
        left = self.remaining.pop(0) if self.remaining else 7000
        client.last_headers = {"x-ratelimit-requests-remaining": str(left)}
        if path == "/players":
            return {"paging": {"total": 1}, "response": [_api_player(9001, self.minutes), _api_player(9002, 450)]}
        if path == "/injuries":
            return {"response": [{"player": {"id": 9001, "type": "Missing Fixture", "reason": "Knee"},
                                  "fixture": {"id": 555, "date": "2026-10-01T15:00:00+00:00"},
                                  "league": {"name": "Premier League"}, "team": {"id": 42}}]}
        if path == "/fixtures":
            return {"response": [{"fixture": {"id": 777, "date": "2026-10-09T19:00:00+00:00"},
                                  "league": {"name": "Premier League"},
                                  "teams": {"home": {"id": 42, "name": "Arsenal"}, "away": {"id": 50, "name": "City"}}}]}
        if path == "/fixtures/players":
            return {"response": [{"team": {"id": 42}, "players": [
                {"player": {"id": 9001}, "statistics": [{"games": {"minutes": 90, "rating": "7.4"}}]}]}]}
        if path == "/leagues" and self.season:
            return {"response": [{"seasons": [{"year": 2025, "current": False}, {"year": self.season, "current": True}]}]}
        if path == "/teams/statistics":
            return {"response": {"fixtures": {"played": {"total": 8}}}}
        return {"response": []}


@pytest_asyncio.fixture
async def league(db):
    from app.world.models import WorldLeague

    db.add(WorldLeague(vendor="api_sports_v3", league_id="39", name="Premier League", season="2025"))
    await db.commit()


def _patch_api(monkeypatch, fake: FakeApi) -> dr.QuotaClient:
    async def _get(self, path, params=None):
        return await fake.get(self, path, params)

    monkeypatch.setattr(ApiFootballClient, "_get", _get)
    client = dr.QuotaClient("key", "http://api", reserve=500, per_minute=100000)
    return client


async def test_refresh_runs_each_step_and_posts_one_slack_message(db, league, monkeypatch, monitoring_db):
    from app.stats.models import PlayerFixtureRating, PlayerInjuryFixture, PlayerStatsSnapshot

    fake = FakeApi()
    client = _patch_api(monkeypatch, fake)
    out = await dr.run_refresh(trigger="cron", steps=["stats", "injuries", "form"], slot=17, client=client)
    assert out["status"] == "succeeded"
    db.expire_all()
    run = await db.get(JobRun, uuid.UUID(str(out["run_id"])))
    assert run.summary["players_created"] == 2 and run.summary["injuries_new"] == 1
    assert run.summary["matches_new"] == 1 and run.summary["ratings"] == 1
    assert run.summary["api_calls"] == len(fake.calls) and run.summary["api_remaining"] == 7000
    steps = (await db.execute(select(JobRun.job, JobRun.status).where(JobRun.parent_id == run.id))).all()
    assert sorted(steps) == [("daily_refresh.form", "succeeded"), ("daily_refresh.injuries", "succeeded"),
                             ("daily_refresh.stats", "succeeded")]
    assert (await db.execute(select(func.count()).select_from(PlayerInjuryFixture))).scalar_one() == 1
    assert (await db.execute(select(func.count()).select_from(PlayerFixtureRating))).scalar_one() == 1
    logs = (await db.execute(select(JobRunLog.message).where(JobRunLog.run_id == run.id))).scalars().all()
    assert any("Stats · Premier League" in m for m in logs)
    assert len(monitoring_db) == 1 and monitoring_db[0].startswith("✅ *Data refresh, 17:00*")

    # A second run: unchanged stats add no snapshots, and the same match isn't fetched again.
    snaps = (await db.execute(select(func.count()).select_from(PlayerStatsSnapshot))).scalar_one()
    fake.calls.clear()
    await dr.run_refresh(trigger="cron", steps=["stats", "form"], slot=22, client=client)
    assert (await db.execute(select(func.count()).select_from(PlayerStatsSnapshot))).scalar_one() == snaps
    assert "/fixtures/players" not in fake.calls


async def test_refresh_moves_a_league_to_the_current_season(db, league, monkeypatch):
    from app.world.models import WorldLeague

    client = _patch_api(monkeypatch, FakeApi(season=2026))
    out = await dr.run_refresh(trigger="cron", steps=["injuries"], slot=17, client=client)
    db.expire_all()
    assert (await db.execute(select(WorldLeague.season))).scalar_one() == "2026"
    run = await db.get(JobRun, uuid.UUID(str(out["run_id"])))
    assert run.summary["seasons_moved"] == ["Premier League 2025→2026"]


async def test_api_football_bugs_are_retried(monkeypatch):
    answers = [{"errors": {"bug": "on our side"}}, {"errors": [], "response": [1]}]

    async def _get(self, path, params=None):
        self.last_headers = {}
        return answers.pop(0)

    monkeypatch.setattr(ApiFootballClient, "_get", _get)
    monkeypatch.setattr(dr, "TRANSIENT_WAIT", 0)
    client = dr.QuotaClient("key", "http://api", reserve=500, per_minute=100000)
    assert (await client._get("/players"))["response"] == [1] and client.calls == 2


async def test_refresh_stops_at_the_quota_reserve_as_partial(db, league, monkeypatch, monitoring_db):
    client = _patch_api(monkeypatch, FakeApi(remaining=[600, 450]))
    out = await dr.run_refresh(trigger="cron", steps=["stats", "injuries", "form"], slot=17, client=client)
    assert out["status"] == "partial"
    db.expire_all()
    run = await db.get(JobRun, uuid.UUID(str(out["run_id"])))
    assert "quota reserve" in run.summary["stopped"]
    assert monitoring_db[0].startswith("⚠️")


async def test_refresh_skips_while_another_is_running(db, monitoring_db):
    db.add(JobRun(job="daily_refresh", trigger="cron", service="worker", status="running",
                  started_at=datetime.now(timezone.utc)))
    await db.commit()
    out = await dr.run_refresh(trigger="manual", steps=["valuations"])
    assert out["status"] == "skipped" and monitoring_db == []


async def test_valuations_step_runs_the_recompute(db, league, monkeypatch):
    async def fake_all(session):
        return {"updated": 12, "skipped_ineligible": 3, "errors": 0, "comparables": 0}

    monkeypatch.setattr("app.valuation.service.compute_all_valuations", fake_all)
    out = await dr.run_refresh(trigger="cron", steps=["valuations"], slot=22)
    db.expire_all()
    run = await db.get(JobRun, uuid.UUID(str(out["run_id"])))
    assert out["status"] == "succeeded" and run.summary["valuations"] == 12


def test_slack_text_names_what_failed():
    text = dr.slack_text("failed", 22, {"failures": ["stats · Serie A: TimeoutError"]}, 61_000, None)
    assert text.startswith("❌ *Data refresh, 22:00* · 1m 01s") and "Serie A" in text and "/admin/jobs" in text


def test_valuation_compute_left_the_web_app():
    from app.main import lifespan  # noqa: F401
    import app.main as main

    assert not hasattr(main, "_valuation_compute_job")


# ── In-app jobs ──────────────────────────────────────────────────────────────


async def test_in_app_job_failure_is_recorded(db):
    from app.common import jobs

    await jobs._record_run("deal_sla", False, RuntimeError("db down"), None)
    row = (await db.execute(select(JobRun).where(JobRun.job == "deal_sla"))).scalar_one()
    assert row.status == "failed" and row.trigger == "scheduler" and "db down" in row.error


# ── Overdue watch ────────────────────────────────────────────────────────────


async def test_overdue_only_once_the_refresh_has_run(db, monitoring_db):
    now = datetime(2026, 12, 2, 18, 0, tzinfo=timezone.utc)  # 18:00 GMT: the 17:00 slot is due
    assert await watch.overdue(now) is None  # never ran: not set up yet
    db.add(JobRun(job="daily_refresh", trigger="cron", service="worker", status="succeeded",
                  started_at=datetime(2026, 12, 1, 22, 0, tzinfo=timezone.utc)))
    await db.commit()
    assert await watch.overdue(now) == datetime(2026, 12, 2, 17, 0, tzinfo=timezone.utc)
    assert (await watch.check(now)).startswith("⏰")
    assert await watch.check(now) is None  # once per slot
    db.add(JobRun(job="daily_refresh", trigger="cron", service="worker", status="succeeded",
                  started_at=datetime(2026, 12, 2, 17, 0, 5, tzinfo=timezone.utc)))
    await db.commit()
    assert await watch.overdue(now) is None


# ── Error tracking ───────────────────────────────────────────────────────────


def _record(msg, *args, level=logging.ERROR, exc=None, name="app.offers.service"):
    rec = logging.LogRecord(name, level, __file__, 1, msg, args, exc)
    return errors.event_from_record(rec, "api")


async def test_errors_group_by_template_and_alert_once(db, monitoring_db):
    sent = await errors.write_events([_record("Offer %s failed for %d", "a1b2", 5),
                                      _record("Offer %s failed for %d", "zz", 9)])
    issue = (await db.execute(select(ErrorIssue))).scalar_one()
    assert issue.count == 2 and issue.status == "open" and len(sent) == 1 and "New error" in sent[0]
    assert await errors.write_events([_record("Offer %s failed for %d", "x", 1)]) == []


async def test_exceptions_group_by_type_and_frame(db):
    def raise_it():
        raise KeyError("thing")
    try:
        raise_it()
    except KeyError:
        exc = sys.exc_info()
    a = _record("first wording", exc=exc)
    b = _record("different wording", exc=exc)
    assert a["fingerprint"] == b["fingerprint"] and a["traceback"]


async def test_resolved_issue_reopens_and_ignored_stays_quiet(db, monitoring_db):
    await errors.write_events([_record("Payment sync broke")])
    issue = (await db.execute(select(ErrorIssue))).scalar_one()
    issue.status = "resolved"
    await db.commit()
    sent = await errors.write_events([_record("Payment sync broke")])
    db.expire_all()
    issue = (await db.execute(select(ErrorIssue))).scalar_one()
    assert issue.status == "open" and "Error is back" in sent[0]
    issue.status = "ignored"
    await db.commit()
    assert await errors.write_events([_record("Payment sync broke")]) == []


async def test_events_are_capped_and_spikes_alert(db, monitoring_db):
    sent = await errors.write_events([_record("Hot loop %d", i) for i in range(errors.SPIKE_COUNT)])
    assert any("Error spike" in s for s in sent)
    issue = (await db.execute(select(ErrorIssue))).scalar_one()
    assert issue.count == errors.SPIKE_COUNT
    events = (await db.execute(select(func.count()).select_from(ErrorEvent))).scalar_one()
    assert events == errors.EVENTS_PER_ISSUE


async def test_warnings_dont_alert(db, monitoring_db):
    assert await errors.write_events([_record("Slow thing", level=logging.WARNING)]) == []


# ── Request health ───────────────────────────────────────────────────────────


async def test_requests_are_counted_per_route_and_flushed(client: AsyncClient, db):
    for _ in range(3):
        await client.get("/health")
    resp = await client.get("/health")
    assert resp.headers.get("x-request-id")
    written = await reqs.flush(everything=True)
    assert written >= 1
    row = (await db.execute(select(RequestMinute).where(RequestMinute.route == "/health"))).scalar_one()
    assert row.count == 4 and row.errors == 0


async def test_error_rate_alert_and_recovery(monitoring_db):
    now = datetime(2026, 10, 10, 12, 0, 30, tzinfo=timezone.utc).timestamp()
    for i in range(1, 6):
        t = now - 60 * i
        for n in range(10):
            reqs.record(t, "GET", "/x", 500 if n < 2 else 200, 5)
    assert (await reqs.check_error_rate(now)).startswith("🔥")
    reqs._totals.clear()
    for i in range(1, 6):
        for n in range(10):
            reqs.record(now - 60 * i, "GET", "/x", 200, 5)
    assert "back to normal" in await reqs.check_error_rate(now)


# ── Retention ────────────────────────────────────────────────────────────────


async def test_retention_deletes_old_rows(db):
    old = datetime.now(timezone.utc) - timedelta(days=100)
    db.add(JobRun(job="x", trigger="cron", service="worker", status="succeeded", started_at=old))
    db.add(RequestMinute(minute=old, method="GET", route="/x", count=1, errors=0, p50_ms=1, p95_ms=1))
    db.add(JobRun(job="y", trigger="cron", service="worker", status="succeeded", started_at=datetime.now(timezone.utc)))
    await db.commit()
    counts = await retention.purge()
    assert counts["job_runs"] == 1 and counts["request_minutes"] == 1
    assert (await db.execute(select(func.count()).select_from(JobRun))).scalar_one() == 1


# ── Admin endpoints ──────────────────────────────────────────────────────────


async def test_admin_pages_are_platform_admins_only(client: AsyncClient):
    club = await _register(client, "notadmin@test.com", club_name="Not Admin FC")
    for path in ("/admin/jobs", "/admin/jobs/runs", "/admin/errors", "/admin/health/requests"):
        assert (await client.get(path, headers=_auth_headers(club))).status_code == 403


async def test_jobs_overview_runs_and_logs(client: AsyncClient, db, admin):
    runs.install_log_capture()
    async with runs.record_run("daily_refresh", trigger="cron") as run:
        logging.getLogger("app.jobs.daily_refresh").warning("Stats for %s failed", "Serie A")
    h = _auth_headers(admin)
    overview = (await client.get("/admin/jobs", headers=h)).json()
    worker = next(j for j in overview["scheduled"] if j["id"] == "daily_refresh")
    assert worker["where"] == "worker" and worker["last_status"] == "succeeded" and worker["next_run_at"]
    listed = (await client.get("/admin/jobs/runs", headers=h)).json()
    assert listed["items"][0]["id"] == str(run.id) and "daily_refresh" in listed["jobs"]
    detail = (await client.get(f"/admin/jobs/runs/{run.id}", headers=h)).json()
    assert detail["log_lines"] == 1
    logs = (await client.get(f"/admin/jobs/runs/{run.id}/logs?level=WARNING", headers=h)).json()
    assert logs["lines"][0]["message"] == "Stats for Serie A failed" and logs["running"] is False


async def test_errors_list_detail_and_resolve(client: AsyncClient, db, admin):
    await errors.write_events([_record("Broken %s", "thing")])
    h = _auth_headers(admin)
    listed = (await client.get("/admin/errors", headers=h)).json()
    assert listed["total"] == 1 and len(listed["items"][0]["last_24h"]) == 24
    issue_id = listed["items"][0]["id"]
    detail = (await client.get(f"/admin/errors/{issue_id}", headers=h)).json()
    assert detail["events"][0]["message"] == "Broken thing"
    resp = await client.patch(f"/admin/errors/{issue_id}", json={"status": "resolved"}, headers=h)
    assert resp.json()["status"] == "resolved"
    assert (await client.get("/admin/errors", headers=h)).json()["total"] == 0


async def test_client_errors_are_kept_without_the_query_and_limited(client: AsyncClient, db):
    from app.monitoring.router import CLIENT_ERRORS_PER_MINUTE, _client_hits

    _client_hits.clear()
    body = {"message": "TypeError: x is undefined", "stack": "TypeError\n at f (app.js:1:2)",
            "path": "/offers/1?token=secret"}
    assert (await client.post("/monitoring/client-errors", json=body)).status_code == 204
    events = await errors.drain()  # noqa: F841
    ev = (await db.execute(select(ErrorEvent))).scalar_one()
    assert ev.context == {"path": "/offers/1"}
    for _ in range(CLIENT_ERRORS_PER_MINUTE + 5):
        await client.post("/monitoring/client-errors", json=body)
    assert len(errors._queue) == CLIENT_ERRORS_PER_MINUTE - 1


async def test_request_health_endpoint(client: AsyncClient, db, admin):
    db.add(RequestMinute(minute=datetime.now(timezone.utc).replace(second=0, microsecond=0), method="GET",
                         route="/offers/{offer_id}", count=10, errors=2, p50_ms=20, p95_ms=300))
    await db.commit()
    data = (await client.get("/admin/health/requests", headers=_auth_headers(admin))).json()
    assert data["total"] == 10 and data["errors"] == 2 and data["failing"][0]["route"] == "/offers/{offer_id}"
    assert len(data["hours"]) == 24


async def test_health_lists_slack_and_the_refresh(client: AsyncClient, admin, monkeypatch):
    monkeypatch.setattr(settings, "slack_webhook_url", None)
    data = (await client.get("/admin/health", headers=_auth_headers(admin))).json()
    keys = {s["key"]: s for s in data["services"]}
    assert keys["slack"]["ok"] is False and "Hasn't run yet" in keys["refresh"]["detail"]


# ── Log hygiene ──────────────────────────────────────────────────────────────

SENSITIVE = ("password", "token", "secret", "wage", "fee")


def test_auth_and_finance_logs_carry_no_secrets_or_money():
    """No logger call in the auth or finance code passes a value whose name
    says it's a password, token, wage or fee."""
    root = Path(__file__).resolve().parent.parent / "app"
    files = list((root / "auth").glob("*.py")) + [root / "clubs" / "service.py", root / "clubs" / "finance.py"]
    offenders = []
    for path in [f for f in files if f.exists()]:
        for node in ast.walk(ast.parse(path.read_text())):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr in ("debug", "info", "warning", "error", "exception", "critical")
                    and isinstance(node.func.value, ast.Name) and node.func.value.id in ("logger", "log", "logging")):
                for arg in node.args[1:]:
                    names = {n.id.lower() for n in ast.walk(arg) if isinstance(n, ast.Name)} | {
                        n.attr.lower() for n in ast.walk(arg) if isinstance(n, ast.Attribute)}
                    if any(word in name for name in names for word in SENSITIVE):
                        offenders.append(f"{path.name}:{node.lineno}")
    assert offenders == []


async def test_run_refresh_now_starts_once(client: AsyncClient, db, admin, monkeypatch):
    import asyncio

    from app.monitoring import router as mon_router

    started: list[dict] = []
    gate = asyncio.Event()

    async def fake_run(**kwargs):
        started.append(kwargs)
        await gate.wait()
        return {"status": "succeeded", "run_id": None}

    monkeypatch.setattr(dr, "run_refresh", fake_run)
    monkeypatch.setattr(mon_router, "_refresh_task", None)
    h = _auth_headers(admin)
    resp = await client.post("/admin/jobs/refresh", json={"valuations": True}, headers=h)
    assert resp.status_code == 202 and resp.json()["steps"] == ["stats", "injuries", "form", "valuations"]
    await asyncio.sleep(0)
    assert started[0]["trigger"] == "manual" and started[0]["user_id"] is not None
    assert (await client.post("/admin/jobs/refresh", json={}, headers=h)).status_code == 409
    gate.set()
    await asyncio.sleep(0)
