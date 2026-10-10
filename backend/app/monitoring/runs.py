"""Record job runs and the log lines written during them.

    async with record_run("daily_refresh", trigger="cron") as run:
        run.summary["leagues"] = 7
        ...                     # run.status = "partial" to say so

A run inserts a `running` row when it starts (committed straight away, so
Admin → Jobs shows it) and updates the row when it ends. Log lines at INFO
and above, written by any logger while the run is current, are kept in
`job_run_logs`, flushed every few seconds so a running job can be followed.
"""
import asyncio
import contextvars
import logging
import time
import traceback
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update

from app import monitoring
from app.monitoring.models import JobRun, JobRunLog

MAX_LOG_LINES = 5000
FLUSH_SECONDS = 5.0
# A run still "running" after this long lost its process (Admin → Jobs: "lost").
LOST_AFTER = timedelta(hours=2)

_current: contextvars.ContextVar[uuid.UUID | None] = contextvars.ContextVar("job_run", default=None)


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Run:
    id: uuid.UUID
    job: str
    status: str | None = None  # set to "partial" (or "skipped") to override "succeeded"
    summary: dict = field(default_factory=dict)
    error: str | None = None


class _Buffer:
    def __init__(self) -> None:
        self.lines: list[dict] = []
        self.kept = 0
        self.dropped = 0


_buffers: dict[uuid.UUID, _Buffer] = {}


class RunLogHandler(logging.Handler):
    """Keeps the lines of whichever run is current in this context."""

    def __init__(self) -> None:
        super().__init__(level=logging.INFO)

    def emit(self, record: logging.LogRecord) -> None:
        run_id = _current.get()
        buf = _buffers.get(run_id) if run_id else None
        if buf is None or record.name.startswith("sqlalchemy"):
            return
        if buf.kept >= MAX_LOG_LINES:
            buf.dropped += 1
            return
        try:
            message = record.getMessage()
        except Exception:  # noqa: BLE001
            message = str(record.msg)
        if record.exc_info:
            message += "\n" + "".join(traceback.format_exception(*record.exc_info))[-1500:]
        buf.lines.append({
            "at": datetime.fromtimestamp(record.created, timezone.utc), "level": record.levelname,
            "logger": record.name[:120], "message": message[:2000],
        })
        buf.kept += 1


_handler: RunLogHandler | None = None


def install_log_capture() -> None:
    """Attach the run log handler to the root logger, once."""
    global _handler
    if _handler is None:
        _handler = RunLogHandler()
        logging.getLogger().addHandler(_handler)
        if logging.getLogger().level > logging.INFO or logging.getLogger().level == logging.NOTSET:
            logging.getLogger().setLevel(logging.INFO)


async def _flush(run_id: uuid.UUID, final: bool = False) -> None:
    buf = _buffers.get(run_id)
    if buf is None:
        return
    lines, buf.lines = buf.lines, []
    if final and buf.dropped:
        lines.append({"at": _now(), "level": "WARNING", "logger": "app.monitoring",
                      "message": f"{buf.dropped} more log lines were not kept (limit {MAX_LOG_LINES} a run)"})
    if not lines:
        return
    async with monitoring.sessions()() as db:
        db.add_all([JobRunLog(run_id=run_id, **line) for line in lines])
        await db.commit()


async def _flusher(run_id: uuid.UUID) -> None:
    while True:
        await asyncio.sleep(FLUSH_SECONDS)
        try:
            await _flush(run_id)
        except Exception:  # noqa: BLE001 — logs are best effort
            pass


async def start_run(job: str, *, trigger: str, parent_id: uuid.UUID | None = None,
                    user_id: uuid.UUID | None = None) -> JobRun:
    row = JobRun(id=uuid.uuid4(), job=job, parent_id=parent_id, trigger=trigger, service=monitoring.service,
                 triggered_by_user_id=user_id, status="running", started_at=_now())
    async with monitoring.sessions()() as db:
        db.add(row)
        await db.commit()
    return row


async def finish_run(run_id: uuid.UUID, *, status: str, started: float, summary: dict | None,
                     error: str | None) -> None:
    async with monitoring.sessions()() as db:
        await db.execute(update(JobRun).where(JobRun.id == run_id).values(
            status=status, finished_at=_now(), duration_ms=int((time.monotonic() - started) * 1000),
            summary=summary or None, error=(error or None) and error[:2000],
        ))
        await db.commit()


@asynccontextmanager
async def record_run(job: str, *, trigger: str, parent_id: uuid.UUID | None = None,
                     user_id: uuid.UUID | None = None, capture_logs: bool = True):
    """Record a run of `job`. An exception marks it failed and propagates."""
    row = await start_run(job, trigger=trigger, parent_id=parent_id, user_id=user_id)
    run = Run(id=row.id, job=job)
    started = time.monotonic()
    token = None
    flusher = None
    if capture_logs:
        _buffers[row.id] = _Buffer()
        token = _current.set(row.id)
        flusher = asyncio.create_task(_flusher(row.id))
    try:
        yield run
    except BaseException as exc:
        await finish_run(row.id, status="failed", started=started, summary=run.summary,
                         error=f"{type(exc).__name__}: {exc}")
        raise
    else:
        await finish_run(row.id, status=run.status or "succeeded", started=started, summary=run.summary,
                         error=run.error)
    finally:
        if capture_logs:
            flusher.cancel()
            _current.reset(token)
            try:
                await _flush(row.id, final=True)
            except Exception:  # noqa: BLE001
                pass
            _buffers.pop(row.id, None)


async def is_running(job: str) -> bool:
    """A run of `job` that started recently and hasn't finished."""
    async with monitoring.sessions()() as db:
        row = (await db.execute(select(JobRun.id).where(
            JobRun.job == job, JobRun.status == "running", JobRun.started_at >= _now() - LOST_AFTER,
        ).limit(1))).first()
    return row is not None


def shown_status(row: JobRun, now: datetime | None = None) -> str:
    """The status to show: a run left "running" too long is "lost"."""
    now = now or _now()
    started = row.started_at if row.started_at.tzinfo else row.started_at.replace(tzinfo=timezone.utc)
    if row.status == "running" and now - started > LOST_AFTER:
        return "lost"
    return row.status
