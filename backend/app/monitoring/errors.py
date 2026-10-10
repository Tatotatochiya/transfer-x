"""Error tracking: warnings and errors from the web app, the worker and
browsers, grouped into issues (docs/feature_spec/scheduled-data-refresh.md).

A logging handler (WARNING and up) turns each record into an event and
queues it; `writer_loop` writes the queue every few seconds, so logging
never waits on the database. Events are grouped by a fingerprint: service,
exception type and the app frame it was raised in, or for a plain log
line, the logger and its message template with numbers, ids and quoted
values stripped out. The newest 20 events of each issue are kept.

Slack hears about a new ERROR issue, a resolved one coming back, and a
spike (50 in 10 minutes) and its end — titles and counts only.
"""
import asyncio
import collections
import hashlib
import logging
import re
import sys
import time
import traceback
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select

from app import monitoring
from app.common import slack
from app.monitoring import context
from app.monitoring.models import ErrorEvent, ErrorIssue

EVENTS_PER_ISSUE = 20
SPIKE_COUNT = 50
SPIKE_WINDOW = 600  # seconds
SKIP = ("app.monitoring", "sqlalchemy", "uvicorn.access", "httpx", "httpcore", "watchfiles", "aiosqlite")
LEVELS = {"WARNING": 30, "ERROR": 40, "CRITICAL": 50}

_queue: collections.deque = collections.deque(maxlen=5000)
_recent: dict[str, collections.deque] = {}
_spiking: set[str] = set()

_UUID = re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I)
_HEX = re.compile(r"\b[0-9a-f]{16,}\b", re.I)
_QUOTED = re.compile(r"(['\"]).*?\1")
_NUM = re.compile(r"\b\d+(\.\d+)?\b")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def normalise(text: str) -> str:
    text = _UUID.sub("<id>", text)
    text = _HEX.sub("<hex>", text)
    text = _QUOTED.sub("<str>", text)
    return _NUM.sub("<n>", text)[:300]


def _app_frame(tb) -> str:
    """The innermost frame in our own code, as 'module:function'."""
    frames = traceback.extract_tb(tb) if tb else []
    for fr in reversed(frames):
        if "/app/" in fr.filename and "/site-packages/" not in fr.filename:
            return f"{fr.filename.rsplit('/app/', 1)[-1]}:{fr.name}"
    return f"{frames[-1].filename.rsplit('/', 1)[-1]}:{frames[-1].name}" if frames else ""


def fingerprint(service: str, logger: str, template: str, exc_type: str | None, frame: str = "") -> str:
    key = f"{service}|{exc_type}|{frame}" if exc_type else f"{service}|{logger}|{normalise(template)}"
    return hashlib.sha1(key.encode()).hexdigest()


def event_from_record(record: logging.LogRecord, service: str) -> dict:
    try:
        message = record.getMessage()
    except Exception:  # noqa: BLE001
        message = str(record.msg)
    template = record.msg if isinstance(record.msg, str) else message
    exc_type, tb_text, frame = None, None, ""
    if record.exc_info and record.exc_info[0] is not None:
        exc_type = record.exc_info[0].__name__
        frame = _app_frame(record.exc_info[2])
        tb_text = "".join(traceback.format_exception(*record.exc_info))[-8000:]
    title = f"{exc_type}: {message}" if exc_type else message
    return {
        "fingerprint": fingerprint(service, record.name, template, exc_type, frame),
        "service": service, "level": record.levelname if record.levelname in LEVELS else "ERROR",
        "logger": record.name[:120], "title": title.splitlines()[0][:300] if title else record.name,
        "message": message[:2000], "traceback": tb_text, "context": context.current(),
        "at": datetime.fromtimestamp(record.created, timezone.utc),
    }


class ErrorCaptureHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__(level=logging.WARNING)

    def emit(self, record: logging.LogRecord) -> None:
        if record.name.startswith(SKIP):
            return
        # The scheduler's timing warnings ("missed by 0:00:01", "maximum
        # number of running instances") are noise for 2-second jobs; a job
        # that fails is recorded by app/common/jobs.py and alerts there.
        if record.name.startswith("apscheduler") and record.levelno < logging.ERROR:
            return
        try:
            _queue.append(event_from_record(record, monitoring.service))
        except Exception:  # noqa: BLE001 — never let error capture raise
            pass


_handler: ErrorCaptureHandler | None = None


def install() -> None:
    """Attach the handler to the root logger and uvicorn's error logger
    (which doesn't propagate to the root), once."""
    global _handler
    if _handler is None:
        _handler = ErrorCaptureHandler()
        logging.getLogger().addHandler(_handler)
        logging.getLogger("uvicorn.error").addHandler(_handler)


def record_client_error(message: str, stack: str | None, path: str | None, user_id: str | None) -> None:
    """A browser error (POST /monitoring/client-errors), grouped under 'web'."""
    first_frame = ""
    for line in (stack or "").splitlines()[1:]:
        line = line.strip()
        if line:
            first_frame = re.sub(r"\?[^:)]*", "", re.sub(r":\d+:\d+", "", line))[:200]
            break
    _queue.append({
        "fingerprint": fingerprint("web", "browser", f"{message}|{first_frame}", None),
        "service": "web", "level": "ERROR", "logger": "browser",
        "title": message.splitlines()[0][:300] or "Browser error", "message": message[:2000],
        "traceback": (stack or "")[:8000] or None,
        "context": {k: v for k, v in {"path": path, "user_id": user_id}.items() if v}, "at": _now(),
    })


def _hour_key(at: datetime) -> str:
    return at.strftime("%Y-%m-%dT%H")


async def write_events(events: list[dict]) -> list[str]:
    """Write queued events. Returns the Slack messages it sent (for tests)."""
    if not events:
        return []
    groups: dict[str, list[dict]] = collections.defaultdict(list)
    for e in events:
        groups[e["fingerprint"]].append(e)
    alerts: list[str] = []
    cutoff = _hour_key(_now() - timedelta(hours=24))
    async with monitoring.sessions()() as db:
        for fp, evs in groups.items():
            evs.sort(key=lambda e: e["at"])
            first, last = evs[0], evs[-1]
            top = max(evs, key=lambda e: LEVELS.get(e["level"], 40))["level"]
            issue = (await db.execute(select(ErrorIssue).where(ErrorIssue.fingerprint == fp))).scalar_one_or_none()
            new = reopened = False
            if issue is None:
                issue = ErrorIssue(fingerprint=fp, service=first["service"], level=top, logger=first["logger"],
                                   title=first["title"], status="open", first_seen=first["at"],
                                   last_seen=last["at"], count=0, hourly={})
                db.add(issue)
                await db.flush()
                new = True
            elif issue.status == "resolved":
                issue.status, reopened = "open", True
            if LEVELS.get(top, 40) > LEVELS.get(issue.level, 40):
                issue.level = top
            issue.last_seen = last["at"]
            issue.count = (issue.count or 0) + len(evs)
            hourly = {k: v for k, v in (issue.hourly or {}).items() if k > cutoff}
            for e in evs:
                hourly[_hour_key(e["at"])] = hourly.get(_hour_key(e["at"]), 0) + 1
            issue.hourly = hourly
            for e in evs[-EVENTS_PER_ISSUE:]:
                db.add(ErrorEvent(issue_id=issue.id, at=e["at"], level=e["level"], message=e["message"],
                                  traceback=e["traceback"], context=e["context"]))
            await db.flush()
            old = (await db.execute(select(ErrorEvent.id).where(ErrorEvent.issue_id == issue.id)
                                    .order_by(ErrorEvent.at.desc(), ErrorEvent.id.desc())
                                    .offset(EVENTS_PER_ISSUE))).scalars().all()
            if old:
                await db.execute(delete(ErrorEvent).where(ErrorEvent.id.in_(old)))
            link = slack.admin_link(f"/admin/errors?issue={issue.id}")
            if issue.status != "ignored" and LEVELS.get(issue.level, 40) >= 40 and (new or reopened):
                word = "New error" if new else "Error is back"
                alerts.append(f"🔴 *{word}* ({issue.service}): {issue.title[:120]} · <{link}|Admin → Errors>")
            # Spikes: SPIKE_COUNT in SPIKE_WINDOW seconds, and when it settles.
            window = _recent.setdefault(fp, collections.deque())
            now = time.monotonic()
            window.extend([now] * len(evs))
            while window and now - window[0] > SPIKE_WINDOW:
                window.popleft()
            if issue.status != "ignored" and len(window) >= SPIKE_COUNT and fp not in _spiking:
                _spiking.add(fp)
                alerts.append(f"📈 *Error spike* ({issue.service}): {issue.title[:120]}, "
                              f"{len(window)} in 10 minutes · <{link}|Admin → Errors>")
        await db.commit()
    for msg in alerts:
        await slack.post(msg)
    return alerts


async def settle_spikes() -> list[str]:
    """Say when a spike has ended (fewer than 10 in the window)."""
    sent = []
    now = time.monotonic()
    for fp in list(_spiking):
        window = _recent.get(fp) or collections.deque()
        while window and now - window[0] > SPIKE_WINDOW:
            window.popleft()
        if len(window) < 10:
            _spiking.discard(fp)
            async with monitoring.sessions()() as db:
                title = (await db.execute(select(ErrorIssue.title).where(ErrorIssue.fingerprint == fp))).scalar()
            msg = f"✅ *Error spike over*: {(title or 'an issue')[:120]}"
            await slack.post(msg)
            sent.append(msg)
    return sent


async def drain() -> list[str]:
    events = []
    while _queue:
        events.append(_queue.popleft())
    try:
        return await write_events(events)
    except Exception as exc:  # noqa: BLE001 — the database may be the thing failing
        print(f"error tracking: couldn't write {len(events)} events: {type(exc).__name__}: {exc}", file=sys.stderr)
        return []


async def writer_loop(every: float = 2.0) -> None:
    ticks = 0
    while True:
        await asyncio.sleep(every)
        await drain()
        ticks += 1
        if ticks % 30 == 0:
            try:
                await settle_spikes()
            except Exception:  # noqa: BLE001
                pass


def reset() -> None:
    """For tests."""
    _queue.clear()
    _recent.clear()
    _spiking.clear()
