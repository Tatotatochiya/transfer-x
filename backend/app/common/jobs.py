"""When each scheduled job last ran, for the admin Health page.

main.py registers `on_job_event` with the scheduler. Kept in memory: it
starts empty when the API restarts, which the page says.
"""
from datetime import datetime, timezone

JOB_LABELS = {
    "close_expired_sales": "Close sales past their deadline",
    "expire_stale_offers": "Expire offers past their deadline",
    "release_held_pushes": "Send pushes held for quiet hours",
    "notify_upcoming_events": "Reminders: offers expiring, auctions ending, instalments due",
    "enrichment_sync": "Player data refresh",
    "valuation_compute": "Recompute model valuations",
    "client_alerts": "Agents' client alerts",
    "approval_expiry": "Expire old approval requests",
    "expire_mandates": "Expire representation mandates",
    "deal_sla": "Flag deals past their paperwork deadline",
    "loan_lifecycle": "Start, end and recall loans",
    "daily_digest": "Daily digest emails",
}

RUNS: dict[str, dict] = {}


def on_job_event(event) -> None:
    """APScheduler listener for EVENT_JOB_EXECUTED and EVENT_JOB_ERROR."""
    RUNS[event.job_id] = {
        "last_run_at": datetime.now(timezone.utc),
        "last_ok": event.exception is None,
        "last_error": str(event.exception)[:300] if event.exception else None,
    }


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
