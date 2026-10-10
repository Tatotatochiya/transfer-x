"""Slack messages for job runs and monitoring alerts, through an Incoming
Webhook (SLACK_WEBHOOK_URL). Never raises: a Slack outage must not fail a
job. Does nothing when the webhook isn't set (dev, tests).

Messages carry titles, counts and durations only — never club names, fees,
bids, tracebacks or player-level deal information."""
import logging
import time

import httpx

from app.config import settings

# The monitoring handler ignores this logger, so a failed post can't loop.
logger = logging.getLogger("app.monitoring.slack")

_last_sent: dict[str, float] = {}


def configured() -> bool:
    return bool(settings.slack_webhook_url)


def admin_link(path: str) -> str:
    return f"{settings.frontend_base_url.rstrip('/')}{path}"


async def post(text: str, *, key: str | None = None, every_seconds: int = 0) -> bool:
    """Post `text` (Slack mrkdwn). With `key`, at most once per `every_seconds`
    for that key. Returns whether a message went out."""
    if not configured():
        return False
    if key and every_seconds:
        now = time.monotonic()
        if now - _last_sent.get(key, -1e12) < every_seconds:
            return False
        _last_sent[key] = now
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(settings.slack_webhook_url, json={"text": text})
        if resp.status_code >= 300:
            logger.info("Slack answered %s", resp.status_code)
            return False
        return True
    except Exception as exc:  # noqa: BLE001
        logger.info("Couldn't post to Slack: %s", type(exc).__name__)
        return False


def reset_limits() -> None:
    """For tests."""
    _last_sent.clear()
