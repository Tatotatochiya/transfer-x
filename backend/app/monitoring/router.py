"""Admin → Jobs, Admin → Errors, request health, and the browser error
intake (docs/feature_spec/scheduled-data-refresh.md). Platform admins only,
except POST /monitoring/client-errors."""
import asyncio
import time
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.database import get_db
from app.deps import get_current_superuser
from app.monitoring.models import ErrorEvent, ErrorIssue, JobRun, JobRunLog, RequestMinute
from app.monitoring.runs import is_running, shown_status

router = APIRouter(tags=["monitoring"])

WORKER_JOBS = [{
    "id": "daily_refresh",
    "label": "Data refresh from API-Football: stats, injuries, match ratings and form",
    "where": "worker",
    "schedule": "17:00 and 22:00 UK · valuations after the 22:00 run",
}]
LEVEL_RANK = {"WARNING": 30, "ERROR": 40, "CRITICAL": 50}
_refresh_task: asyncio.Task | None = None


def _iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)).isoformat()


def _run_out(r: JobRun) -> dict:
    return {
        "id": str(r.id), "job": r.job, "parent_id": str(r.parent_id) if r.parent_id else None,
        "trigger": r.trigger, "service": r.service, "status": shown_status(r),
        "started_at": _iso(r.started_at), "finished_at": _iso(r.finished_at), "duration_ms": r.duration_ms,
        "summary": r.summary, "error": r.error,
        "triggered_by_user_id": str(r.triggered_by_user_id) if r.triggered_by_user_id else None,
    }


def _next_refresh(now: datetime) -> datetime:
    from app.jobs.daily_refresh import LONDON, SLOTS

    local = now.astimezone(LONDON)
    for days in (0, 1):
        day = (local + timedelta(days=days)).date()
        for hour in SLOTS:
            slot = datetime(day.year, day.month, day.day, hour, tzinfo=LONDON)
            if slot > local:
                return slot.astimezone(timezone.utc)
    return now


# ── Jobs ─────────────────────────────────────────────────────────────────────


@router.get("/admin/jobs")
async def jobs_overview(db: AsyncSession = Depends(get_db), _: User = Depends(get_current_superuser)) -> dict:
    """Every scheduled job (worker and web app), what's running, and the
    latest runs."""
    from app.common.jobs import JOB_LABELS, RUNS, STARTED, every, saved_runs
    from app.monitoring import watch

    now = datetime.now(timezone.utc)
    scheduled = []
    for wj in WORKER_JOBS:
        last = (await db.execute(select(JobRun).where(JobRun.job == wj["id"], JobRun.parent_id.is_(None),
                                                      JobRun.status != "skipped")
                                 .order_by(JobRun.started_at.desc()).limit(1))).scalar_one_or_none()
        missed = await watch.overdue(now)
        scheduled.append({
            **wj, "last_run_at": _iso(last.started_at) if last else None,
            "last_status": shown_status(last) if last else None, "last_error": last.error if last else None,
            "next_run_at": _iso(_next_refresh(now)), "running": bool(last and shown_status(last) == "running"),
            "overdue_since": _iso(missed),
        })
    saved = await saved_runs(db)
    try:
        from app.main import _scheduler

        app_jobs = sorted(_scheduler.get_jobs(), key=lambda j: j.id)
    except Exception:  # noqa: BLE001
        app_jobs = []
    for job in app_jobs:
        run = RUNS.get(job.id) or saved.get(job.id, {})
        last_ok = run.get("last_ok")
        scheduled.append({
            "id": job.id, "label": JOB_LABELS.get(job.id, job.id.replace("_", " ").capitalize()),
            "where": "web app", "schedule": f"every {every(job.trigger)}",
            "last_run_at": _iso(run.get("last_run_at")),
            "last_status": None if last_ok is None else ("succeeded" if last_ok else "failed"),
            "last_error": run.get("last_error"), "next_run_at": _iso(job.next_run_time),
            "running": job.id in STARTED, "overdue_since": None,
        })

    running_rows = (await db.execute(select(JobRun).where(JobRun.status == "running", JobRun.parent_id.is_(None))
                                     .order_by(JobRun.started_at.desc()))).scalars().all()
    running = [_run_out(r) for r in running_rows]
    for job_id, (_, started_at) in STARTED.items():
        running.append({"id": None, "job": job_id, "trigger": "scheduler", "service": "api", "status": "running",
                        "started_at": _iso(started_at), "label": JOB_LABELS.get(job_id, job_id)})
    return {"scheduled": scheduled, "running": running, "checked_at": _iso(now)}


@router.get("/admin/jobs/runs")
async def list_runs(
    job: str | None = None,
    status_: str | None = Query(None, alias="status"),
    include_steps: bool = False,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superuser),
) -> dict:
    q = select(JobRun)
    if job:
        q = q.where(JobRun.job == job)
    if not include_steps:
        q = q.where(JobRun.parent_id.is_(None))
    if status_ == "lost":
        q = q.where(JobRun.status == "running", JobRun.started_at < datetime.now(timezone.utc) - timedelta(hours=2))
    elif status_:
        q = q.where(JobRun.status == status_)
    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar_one()
    rows = (await db.execute(q.order_by(JobRun.started_at.desc()).limit(limit).offset(offset))).scalars().all()
    jobs = sorted(set((await db.execute(select(JobRun.job).where(JobRun.parent_id.is_(None)).distinct())).scalars()))
    return {"items": [_run_out(r) for r in rows], "total": total, "jobs": jobs}


@router.get("/admin/jobs/runs/{run_id}")
async def get_run(run_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                  _: User = Depends(get_current_superuser)) -> dict:
    row = await db.get(JobRun, run_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    steps = (await db.execute(select(JobRun).where(JobRun.parent_id == run_id)
                              .order_by(JobRun.started_at))).scalars().all()
    lines = (await db.execute(select(func.count()).select_from(JobRunLog).where(JobRunLog.run_id == run_id))).scalar_one()
    return {**_run_out(row), "steps": [_run_out(s) for s in steps], "log_lines": lines}


@router.get("/admin/jobs/runs/{run_id}/logs")
async def run_logs(
    run_id: uuid.UUID,
    after: int = 0,
    level: str | None = Query(None, pattern="^(WARNING|ERROR)$"),
    q: str | None = Query(None, max_length=200),
    limit: int = Query(500, ge=1, le=2000),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superuser),
) -> dict:
    """Log lines after id `after` (for the live tail), oldest first."""
    stmt = select(JobRunLog).where(JobRunLog.run_id == run_id, JobRunLog.id > after)
    if level == "WARNING":
        stmt = stmt.where(JobRunLog.level.in_(["WARNING", "ERROR", "CRITICAL"]))
    elif level == "ERROR":
        stmt = stmt.where(JobRunLog.level.in_(["ERROR", "CRITICAL"]))
    if q:
        stmt = stmt.where(JobRunLog.message.ilike(f"%{q}%"))
    rows = (await db.execute(stmt.order_by(JobRunLog.id).limit(limit))).scalars().all()
    run = await db.get(JobRun, run_id)
    return {
        "lines": [{"id": r.id, "at": _iso(r.at), "level": r.level, "logger": r.logger, "message": r.message}
                  for r in rows],
        "running": bool(run and shown_status(run) == "running"),
    }


class RefreshRequest(BaseModel):
    valuations: bool = False


@router.post("/admin/jobs/refresh", status_code=status.HTTP_202_ACCEPTED)
async def run_refresh_now(body: RefreshRequest, current_user: User = Depends(get_current_superuser)) -> dict:
    """Start the data refresh in the web app, now (Admin → Jobs). Same job,
    same lock, recorded as a manual run."""
    global _refresh_task
    from app.jobs.daily_refresh import JOB, run_refresh

    if (_refresh_task and not _refresh_task.done()) or await is_running(JOB):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A data refresh is already running")
    steps = ["stats", "injuries", "form"] + (["valuations"] if body.valuations else [])
    _refresh_task = asyncio.create_task(run_refresh(trigger="manual", steps=steps, user_id=current_user.id))
    return {"started": True, "steps": steps}


# ── Errors ───────────────────────────────────────────────────────────────────


def _sparkline(hourly: dict | None, now: datetime) -> list[int]:
    hourly = hourly or {}
    return [hourly.get((now - timedelta(hours=23 - i)).strftime("%Y-%m-%dT%H"), 0) for i in range(24)]


def _issue_out(i: ErrorIssue, now: datetime) -> dict:
    return {
        "id": str(i.id), "service": i.service, "level": i.level, "logger": i.logger, "title": i.title,
        "status": i.status, "first_seen": _iso(i.first_seen), "last_seen": _iso(i.last_seen), "count": i.count,
        "last_24h": _sparkline(i.hourly, now),
    }


@router.get("/admin/errors")
async def list_issues(
    status_: str | None = Query("open", alias="status", pattern="^(open|resolved|ignored|all)$"),
    service: str | None = Query(None, pattern="^(api|worker|web)$"),
    level: str | None = Query(None, pattern="^(WARNING|ERROR)$"),
    q: str | None = Query(None, max_length=200),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superuser),
) -> dict:
    stmt = select(ErrorIssue)
    if status_ and status_ != "all":
        stmt = stmt.where(ErrorIssue.status == status_)
    if service:
        stmt = stmt.where(ErrorIssue.service == service)
    if level == "ERROR":
        stmt = stmt.where(ErrorIssue.level.in_(["ERROR", "CRITICAL"]))
    elif level == "WARNING":
        stmt = stmt.where(ErrorIssue.level == "WARNING")
    if q:
        stmt = stmt.where(or_(ErrorIssue.title.ilike(f"%{q}%"), ErrorIssue.logger.ilike(f"%{q}%")))
    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = (await db.execute(stmt.order_by(ErrorIssue.last_seen.desc()).limit(limit).offset(offset))).scalars().all()
    now = datetime.now(timezone.utc)
    counts = dict((await db.execute(select(ErrorIssue.status, func.count()).group_by(ErrorIssue.status))).all())
    return {"items": [_issue_out(i, now) for i in rows], "total": total, "counts": counts}


@router.get("/admin/errors/{issue_id}")
async def get_issue(issue_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                    _: User = Depends(get_current_superuser)) -> dict:
    issue = await db.get(ErrorIssue, issue_id)
    if issue is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found")
    events = (await db.execute(select(ErrorEvent).where(ErrorEvent.issue_id == issue_id)
                               .order_by(ErrorEvent.at.desc(), ErrorEvent.id.desc()))).scalars().all()
    return {**_issue_out(issue, datetime.now(timezone.utc)), "events": [
        {"id": e.id, "at": _iso(e.at), "level": e.level, "message": e.message, "traceback": e.traceback,
         "context": e.context} for e in events]}


class IssueUpdate(BaseModel):
    status: str = Field(pattern="^(open|resolved|ignored)$")


@router.patch("/admin/errors/{issue_id}")
async def update_issue(issue_id: uuid.UUID, body: IssueUpdate, db: AsyncSession = Depends(get_db),
                       _: User = Depends(get_current_superuser)) -> dict:
    issue = await db.get(ErrorIssue, issue_id)
    if issue is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found")
    issue.status = body.status
    await db.commit()
    return _issue_out(issue, datetime.now(timezone.utc))


# ── Request health ───────────────────────────────────────────────────────────


@router.get("/admin/health/requests")
async def request_health(hours: int = Query(24, ge=1, le=336), db: AsyncSession = Depends(get_db),
                         _: User = Depends(get_current_superuser)) -> dict:
    """Requests, 5xx and latency over the last `hours`: per hour, and the
    slowest and most-failing endpoints."""
    now = datetime.now(timezone.utc)
    since = now - timedelta(hours=hours)
    rows = (await db.execute(select(RequestMinute).where(RequestMinute.minute >= since))).scalars().all()
    by_hour: dict[str, list[int]] = {}
    routes: dict[tuple[str, str], dict] = {}
    for r in rows:
        minute = r.minute if r.minute.tzinfo else r.minute.replace(tzinfo=timezone.utc)
        h = by_hour.setdefault(minute.strftime("%Y-%m-%dT%H:00:00+00:00"), [0, 0])
        h[0] += r.count
        h[1] += r.errors
        agg = routes.setdefault((r.method, r.route), {"count": 0, "errors": 0, "p95_weighted": 0.0, "p95_max": 0})
        agg["count"] += r.count
        agg["errors"] += r.errors
        agg["p95_weighted"] += r.p95_ms * r.count
        agg["p95_max"] = max(agg["p95_max"], r.p95_ms)
    endpoints = [{"method": m, "route": rt, "count": a["count"], "errors": a["errors"],
                  "p95_ms": int(a["p95_weighted"] / a["count"]) if a["count"] else 0, "p95_max_ms": a["p95_max"]}
                 for (m, rt), a in routes.items()]
    total = sum(e["count"] for e in endpoints)
    errors = sum(e["errors"] for e in endpoints)
    hours_out = []
    for i in range(hours):
        key = (now - timedelta(hours=hours - 1 - i)).strftime("%Y-%m-%dT%H:00:00+00:00")
        c, e = by_hour.get(key, [0, 0])
        hours_out.append({"hour": key, "count": c, "errors": e})
    return {
        "hours": hours_out, "total": total, "errors": errors,
        "error_rate": round(errors / total, 4) if total else 0.0,
        "slowest": sorted([e for e in endpoints if e["count"] >= 5], key=lambda e: -e["p95_ms"])[:10],
        "failing": sorted([e for e in endpoints if e["errors"]], key=lambda e: -e["errors"])[:10],
    }


# ── Browser errors ───────────────────────────────────────────────────────────

CLIENT_ERRORS_PER_MINUTE = 20
_client_hits: dict[str, list[float]] = {}


class ClientError(BaseModel):
    message: str = Field(max_length=2000)
    stack: str | None = Field(None, max_length=8000)
    path: str | None = Field(None, max_length=300)


@router.post("/monitoring/client-errors", status_code=status.HTTP_204_NO_CONTENT)
async def client_error(body: ClientError, request: Request, authorization: str | None = Header(None)) -> None:
    """A browser error from the frontend. Signed in or not; limited per user
    or address. Only the path is kept, never the query."""
    from app.auth import service as auth_service
    from app.monitoring import errors

    user_id = None
    if authorization and authorization.lower().startswith("bearer "):
        try:
            user_id = auth_service.decode_access_token(authorization[7:]).get("sub")
        except Exception:  # noqa: BLE001
            user_id = None
    key = user_id or (request.client.host if request.client else "unknown")
    now = time.monotonic()
    hits = [t for t in _client_hits.get(key, []) if now - t < 60]
    if len(hits) >= CLIENT_ERRORS_PER_MINUTE:
        _client_hits[key] = hits
        return None
    hits.append(now)
    _client_hits[key] = hits
    path = (body.path or "").split("?", 1)[0].split("#", 1)[0] or None
    errors.record_client_error(body.message, body.stack, path, user_id)
    return None
