"""Request health: count, 5xx and latency per endpoint per minute, kept in
memory and written every 30 seconds to `request_minutes` (14 days).

The middleware also sets the request context error events carry, gives each
request an id (the X-Request-ID response header), and logs an uncaught
exception with its route, so error tracking sees it.
"""
import asyncio
import logging
import time
import uuid
from datetime import datetime, timedelta, timezone

from app import monitoring
from app.common import slack
from app.monitoring import context
from app.monitoring.models import RequestMinute

logger = logging.getLogger("app.requests")
SAMPLES = 1000           # latencies kept per endpoint-minute for p50/p95
ERROR_RATE = 0.05        # 5xx share that alerts…
ERROR_RATE_MINUTES = 5   # …over this many minutes…
ERROR_RATE_MIN_REQUESTS = 20  # …with at least this many requests

# (minute, method, route) → [count, errors, [latency ms…]]
_minutes: dict[tuple[datetime, str, str], list] = {}
# minute → [count, errors], the last hour, for the error-rate alert
_totals: dict[datetime, list] = {}
_alerting = False


def _minute(ts: float) -> datetime:
    return datetime.fromtimestamp(ts - ts % 60, timezone.utc)


def record(started: float, method: str, route: str, status: int, ms: float) -> None:
    key = (_minute(started), method, route[:200])
    row = _minutes.setdefault(key, [0, 0, []])
    row[0] += 1
    if status >= 500:
        row[1] += 1
    if len(row[2]) < SAMPLES:
        row[2].append(ms)
    tot = _totals.setdefault(key[0], [0, 0])
    tot[0] += 1
    tot[1] += status >= 500


def _pct(values: list[float], p: float) -> int:
    if not values:
        return 0
    v = sorted(values)
    return int(round(v[min(len(v) - 1, int(p * (len(v) - 1) + 0.5))]))


async def flush(now: float | None = None, everything: bool = False) -> int:
    """Write the finished minutes. Returns the rows written."""
    current = _minute(now or time.time())
    done = [k for k in _minutes if everything or k[0] < current]
    if not done:
        return 0
    rows = []
    for k in done:
        count, errors, lat = _minutes.pop(k)
        rows.append(RequestMinute(minute=k[0], method=k[1], route=k[2], count=count, errors=errors,
                                  p50_ms=_pct(lat, 0.5), p95_ms=_pct(lat, 0.95)))
    async with monitoring.sessions()() as db:
        db.add_all(rows)
        await db.commit()
    for m in [m for m in _totals if m < current - timedelta(hours=1)]:
        del _totals[m]
    return len(rows)


async def check_error_rate(now: float | None = None) -> str | None:
    """Alert when 5xx passes 5% over the last five finished minutes; say
    when it recovers. Returns the message sent, if any."""
    global _alerting
    current = _minute(now or time.time())
    window = [_totals.get(current - timedelta(minutes=i), [0, 0]) for i in range(1, ERROR_RATE_MINUTES + 1)]
    count, errors = sum(w[0] for w in window), sum(w[1] for w in window)
    rate = errors / count if count else 0.0
    msg = None
    if not _alerting and count >= ERROR_RATE_MIN_REQUESTS and rate > ERROR_RATE:
        _alerting = True
        msg = (f"🔥 *Server errors at {rate:.0%}* of requests over {ERROR_RATE_MINUTES} minutes "
               f"({errors} of {count}) · <{slack.admin_link('/admin/health')}|Admin → Health>")
    elif _alerting and rate <= ERROR_RATE / 2:
        _alerting = False
        msg = f"✅ *Server errors back to normal* ({rate:.1%} over {ERROR_RATE_MINUTES} minutes)"
    if msg:
        await slack.post(msg)
    return msg


async def flush_loop(every: float = 30.0) -> None:
    while True:
        await asyncio.sleep(every)
        try:
            await flush()
            await check_error_rate()
        except Exception:  # noqa: BLE001 — health figures are best effort
            pass


def reset() -> None:
    global _alerting
    _minutes.clear()
    _totals.clear()
    _alerting = False


class MonitoringMiddleware:
    """Pure ASGI, so streaming responses and websockets pass straight through."""

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope.get("method") == "OPTIONS":
            await self.app(scope, receive, send)
            return
        request_id = uuid.uuid4().hex[:12]
        ctx = {"method": scope.get("method"), "path": scope.get("path"), "request_id": request_id}
        token = context.request_ctx.set(ctx)
        started_wall, started = time.time(), time.monotonic()
        status = {"code": 500}

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                status["code"] = message["status"]
                ctx["status"] = message["status"]
                message.setdefault("headers", [])
                message["headers"] = list(message["headers"]) + [(b"x-request-id", request_id.encode())]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception:
            route = getattr(scope.get("route"), "path", None) or scope.get("path", "")
            ctx["status"] = 500
            logger.error("Unhandled error on %s %s", scope.get("method"), route, exc_info=True)
            status["code"] = 500
            raise
        finally:
            route = getattr(scope.get("route"), "path", None) or "(no route)"
            record(started_wall, scope.get("method", ""), route, status["code"],
                   (time.monotonic() - started) * 1000)
            context.request_ctx.reset(token)
