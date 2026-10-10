"""When each scheduled job last ran, for the admin Health page.

main.py registers `on_job_event` with the scheduler. The last run of each
job is kept in memory and saved to `scheduler_job_runs` (migration 0092),
so the page still knows after a restart. Saving is throttled: the 2-second
job would otherwise write every 2 seconds.
"""
import asyncio
import logging
import time as _time
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

logger = logging.getLogger(__name__)
SAVE_EVERY_SECONDS = 60


class SchedulerJobRun(Base):
    __tablename__ = "scheduler_job_runs"

    job_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    last_run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_ok: Mapped[bool] = mapped_column(Boolean, nullable=False)
    last_error: Mapped[str | None] = mapped_column(String(300), nullable=True)
    last_failure_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

JOB_LABELS = {
    "close_expired_sales": "Close sales past their deadline",
    "expire_stale_offers": "Expire offers past their deadline",
    "release_held_pushes": "Send pushes held for quiet hours",
    "execute_held_actions": "Send Lite actions once their undo window closes",
    "morning_summary": "Morning summary pushes",
    "email_fallback": "Emails for unread \"your move\" pushes after 30 minutes",
    "notify_upcoming_events": "Reminders: offers expiring, auctions ending, instalments due",
    "enrichment_sync": "Player data refresh",
    "refresh_watch": "Check the data refresh ran on time",
    "monitoring_retention": "Delete old run logs, errors and request figures",
    "client_alerts": "Agents' client alerts",
    "approval_expiry": "Expire old approval requests",
    "expire_mandates": "Expire representation mandates",
    "deal_sla": "Flag deals past their paperwork deadline",
    "loan_lifecycle": "Start, end and recall loans",
    "daily_digest": "Daily digest emails",
}

# Jobs that run at least this often record only failures and the first
# success after one in job_runs; less frequent jobs record every run.
EVERY_RUN_FROM_SECONDS = 3600

RUNS: dict[str, dict] = {}
# When each job's current run started (EVENT_JOB_SUBMITTED): Admin → Jobs'
# "running now", and the run's duration.
STARTED: dict[str, tuple[float, datetime]] = {}
_saved: dict[str, tuple[float, bool]] = {}  # job → (monotonic time saved, outcome saved)
_tasks: set = set()


def on_job_submitted(event) -> None:
    """APScheduler listener for EVENT_JOB_SUBMITTED."""
    STARTED[event.job_id] = (_time.monotonic(), datetime.now(timezone.utc))


def _interval_seconds(job_id: str) -> int:
    try:
        from app.main import _scheduler

        job = _scheduler.get_job(job_id)
        interval = getattr(job.trigger, "interval", None) if job else None
        return int(interval.total_seconds()) if interval else 0
    except Exception:  # noqa: BLE001
        return 0


def _spawn(coro) -> None:
    try:
        task = asyncio.get_running_loop().create_task(coro)
        _tasks.add(task)
        task.add_done_callback(_tasks.discard)
    except RuntimeError:  # no running loop (tests, scripts)
        coro.close()


def on_job_event(event) -> None:
    """APScheduler listener for EVENT_JOB_EXECUTED and EVENT_JOB_ERROR."""
    ok = event.exception is None
    previous_ok = (RUNS.get(event.job_id) or {}).get("last_ok")
    started = STARTED.pop(event.job_id, None)
    if ok is False or previous_ok is False or _interval_seconds(event.job_id) >= EVERY_RUN_FROM_SECONDS:
        _spawn(_record_run(event.job_id, ok, event.exception, started))
    if not ok:
        from app.common import slack

        label = JOB_LABELS.get(event.job_id, event.job_id)
        _spawn(slack.post(
            f"❌ *Scheduled job failed*: {label} · {type(event.exception).__name__}: {str(event.exception)[:150]}"
            f" · <{slack.admin_link('/admin/jobs')}|Admin → Jobs>",
            key=f"job-fail:{event.job_id}", every_seconds=3600))
    elif previous_ok is False:
        from app.common import slack

        _spawn(slack.post(f"✅ *Scheduled job recovered*: {JOB_LABELS.get(event.job_id, event.job_id)}"))
    run = {
        "last_run_at": datetime.now(timezone.utc),
        "last_ok": ok,
        "last_error": str(event.exception)[:300] if event.exception else None,
    }
    RUNS[event.job_id] = run
    saved = _saved.get(event.job_id)
    if saved is None or saved[1] != ok or _time.monotonic() - saved[0] >= SAVE_EVERY_SECONDS:
        _saved[event.job_id] = (_time.monotonic(), ok)
        try:
            task = asyncio.get_running_loop().create_task(_save(event.job_id, run))
            _tasks.add(task)
            task.add_done_callback(_tasks.discard)
        except RuntimeError:  # no running loop (tests, scripts)
            pass


async def _record_run(job_id: str, ok: bool, exc: BaseException | None,
                      started: tuple[float, datetime] | None) -> None:
    """One job_runs row for an in-app scheduler job's run."""
    import uuid

    from app import monitoring
    from app.monitoring.models import JobRun

    now = datetime.now(timezone.utc)
    try:
        async with monitoring.sessions()() as db:
            db.add(JobRun(
                id=uuid.uuid4(), job=job_id, trigger="scheduler", service="api",
                status="succeeded" if ok else "failed",
                started_at=started[1] if started else now, finished_at=now,
                duration_ms=int((_time.monotonic() - started[0]) * 1000) if started else None,
                error=f"{type(exc).__name__}: {exc}"[:2000] if exc else None,
            ))
            await db.commit()
    except Exception:
        logger.info("Couldn't record the run of %s", job_id)


async def _save(job_id: str, run: dict) -> None:
    from app.database import AsyncSessionLocal

    try:
        async with AsyncSessionLocal() as db:
            row = await db.get(SchedulerJobRun, job_id)
            if row is None:
                row = SchedulerJobRun(job_id=job_id, last_run_at=run["last_run_at"], last_ok=run["last_ok"])
                db.add(row)
            row.last_run_at = run["last_run_at"]
            row.last_ok = run["last_ok"]
            row.last_error = run["last_error"]
            if not run["last_ok"]:
                row.last_failure_at = run["last_run_at"]
            await db.commit()
    except Exception:
        logger.exception("Couldn't save the last run of %s", job_id)


async def saved_runs(db) -> dict[str, dict]:
    """The saved last run of every job, for after a restart."""
    from sqlalchemy import select

    rows = (await db.execute(select(SchedulerJobRun))).scalars()
    return {r.job_id: {"last_run_at": r.last_run_at, "last_ok": r.last_ok, "last_error": r.last_error} for r in rows}


def every(trigger) -> str:
    """'1 minute', '5 minutes', '24 hours' from an interval trigger."""
    seconds = int(getattr(trigger, "interval", None).total_seconds()) if getattr(trigger, "interval", None) else 0
    if not seconds:
        return str(trigger)
    for unit, size in (("hour", 3600), ("minute", 60), ("second", 1)):
        if seconds % size == 0:
            n = seconds // size
            return f"{n} {unit}{'s' if n != 1 else ''}"
    return f"{seconds} seconds"
