"""Delete monitoring data past its retention (the spec's privacy section)."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete

from app import monitoring
from app.monitoring.models import ErrorEvent, ErrorIssue, JobRun, JobRunLog, RequestMinute

KEEP = {
    "job_runs": timedelta(days=90),
    "job_run_logs": timedelta(days=30),
    "error_events": timedelta(days=30),
    "error_issues": timedelta(days=90),   # after last seen
    "request_minutes": timedelta(days=14),
}


async def purge(now: datetime | None = None) -> dict[str, int]:
    now = now or datetime.now(timezone.utc)
    out = {}
    async with monitoring.sessions()() as db:
        for name, stmt in (
            ("job_run_logs", delete(JobRunLog).where(JobRunLog.at < now - KEEP["job_run_logs"])),
            ("job_runs", delete(JobRun).where(JobRun.started_at < now - KEEP["job_runs"])),
            ("error_events", delete(ErrorEvent).where(ErrorEvent.at < now - KEEP["error_events"])),
            ("error_issues", delete(ErrorIssue).where(ErrorIssue.last_seen < now - KEEP["error_issues"])),
            ("request_minutes", delete(RequestMinute).where(RequestMinute.minute < now - KEEP["request_minutes"])),
        ):
            out[name] = (await db.execute(stmt)).rowcount or 0
        await db.commit()
    return out
