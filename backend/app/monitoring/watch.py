"""Is the scheduled refresh running on time? Checked hourly in the web app,
because a cron run that never starts can't report on itself."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app import monitoring
from app.common import slack
from app.monitoring.models import JobRun

GRACE = timedelta(minutes=45)
_alerted: set[datetime] = set()


def last_due_slot(now: datetime) -> datetime:
    """The latest 17:00 or 22:00 UK slot at least GRACE ago, in UTC."""
    from app.jobs.daily_refresh import LONDON, SLOTS

    local = now.astimezone(LONDON)
    candidates = []
    for days_back in (0, 1):
        day = (local - timedelta(days=days_back)).date()
        for hour in SLOTS:
            slot = datetime(day.year, day.month, day.day, hour, tzinfo=LONDON).astimezone(timezone.utc)
            if slot + GRACE <= now:
                candidates.append(slot)
    return max(candidates)


async def overdue(now: datetime | None = None) -> datetime | None:
    """The missed slot, when the refresh has run before but not for the
    latest slot. None when it's on time, or has never run (not set up yet)."""
    from app.jobs.daily_refresh import JOB

    now = now or datetime.now(timezone.utc)
    slot = last_due_slot(now)
    async with monitoring.sessions()() as db:
        latest = (await db.execute(select(JobRun.started_at).where(JobRun.job == JOB, JobRun.trigger == "cron")
                                   .order_by(JobRun.started_at.desc()).limit(1))).scalar()
    if latest is None:
        return None
    latest = latest if latest.tzinfo else latest.replace(tzinfo=timezone.utc)
    return slot if latest < slot - timedelta(minutes=10) else None


async def check(now: datetime | None = None) -> str | None:
    slot = await overdue(now)
    if slot is None or slot in _alerted:
        return None
    _alerted.add(slot)
    from app.jobs.daily_refresh import LONDON

    when = slot.astimezone(LONDON).strftime("%H:%M on %a %d %b")
    msg = (f"⏰ *Data refresh didn't run*: nothing for the {when} slot (UK time). "
           f"Check the stats-worker service on Railway · <{slack.admin_link('/admin/jobs')}|Admin → Jobs>")
    await slack.post(msg)
    return msg
