"""Analytics service — ingest and admin reporting queries."""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, distinct, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.models import AnalyticsEvent, EventType
from app.analytics.schemas import (
    AnalyticsEventIn,
    AnalyticsOverview,
    DailyCount,
    SessionRow,
    TopPage,
    UserActivityRow,
)


# ── Ingest ────────────────────────────────────────────────────────────────────


async def record_events(
    db: AsyncSession,
    events: list[AnalyticsEventIn],
    user_id: uuid.UUID | None,
    ip_address: str | None,
    user_agent: str | None,
) -> None:
    rows = [
        AnalyticsEvent(
            id=uuid.uuid4(),
            session_id=uuid.UUID(str(e.session_id)),
            user_id=uuid.UUID(str(user_id)) if user_id else None,
            ip_address=ip_address,
            user_agent=user_agent,
            event_type=e.event_type,
            path=e.path,
            referrer=e.referrer,
            element=e.element,
            duration_ms=e.duration_ms,
            meta=e.meta,
        )
        for e in events
    ]
    db.add_all(rows)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _days_ago(n: int) -> datetime:
    return _now_utc() - timedelta(days=n)


def _today_start() -> datetime:
    now = _now_utc()
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


# ── Admin queries ─────────────────────────────────────────────────────────────


async def get_overview(db: AsyncSession) -> AnalyticsOverview:
    today = _today_start()
    d7 = _days_ago(7)
    d30 = _days_ago(30)

    async def _count(since: datetime, event_type: EventType | None = None) -> int:
        q = select(func.count()).select_from(AnalyticsEvent).where(AnalyticsEvent.created_at >= since)
        if event_type:
            q = q.where(AnalyticsEvent.event_type == event_type)
        return (await db.execute(q)).scalar_one()

    async def _unique_sessions(since: datetime) -> int:
        q = (
            select(func.count(distinct(AnalyticsEvent.session_id)))
            .where(AnalyticsEvent.created_at >= since)
        )
        return (await db.execute(q)).scalar_one()

    async def _dau(since: datetime) -> int:
        q = (
            select(func.count(distinct(AnalyticsEvent.user_id)))
            .where(AnalyticsEvent.created_at >= since)
            .where(AnalyticsEvent.user_id.isnot(None))
        )
        return (await db.execute(q)).scalar_one()

    # avg DAU over last 7 days = distinct (date, user_id) pairs / 7
    dau_7d_q = text(
        "SELECT COUNT(DISTINCT (DATE(created_at AT TIME ZONE 'UTC'), user_id)) / 7.0 "
        "FROM analytics_events "
        "WHERE created_at >= :since AND user_id IS NOT NULL"
    )
    dau_7d_raw = (await db.execute(dau_7d_q, {"since": _days_ago(7)})).scalar()
    dau_7d = int(dau_7d_raw or 0)

    return AnalyticsOverview(
        total_events_today=await _count(today),
        total_events_7d=await _count(d7),
        total_events_30d=await _count(d30),
        unique_sessions_today=await _unique_sessions(today),
        unique_sessions_7d=await _unique_sessions(d7),
        dau_today=await _dau(today),
        dau_7d=dau_7d,
        page_views_today=await _count(today, EventType.PAGE_VIEW),
        page_views_7d=await _count(d7, EventType.PAGE_VIEW),
    )


async def get_top_pages(
    db: AsyncSession, days: int = 7, limit: int = 20
) -> list[TopPage]:
    since = _days_ago(days)
    q = (
        select(
            AnalyticsEvent.path,
            func.count().label("views"),
            func.count(distinct(AnalyticsEvent.session_id)).label("unique_sessions"),
        )
        .where(AnalyticsEvent.created_at >= since)
        .where(AnalyticsEvent.event_type == EventType.PAGE_VIEW)
        .group_by(AnalyticsEvent.path)
        .order_by(func.count().desc())
        .limit(limit)
    )
    rows = (await db.execute(q)).fetchall()

    # Get avg durations from PAGE_LEAVE events for the same paths
    paths = [r.path for r in rows]
    avg_dur: dict[str, float | None] = {}
    if paths:
        dur_q = (
            select(
                AnalyticsEvent.path,
                func.avg(AnalyticsEvent.duration_ms).label("avg_dur"),
            )
            .where(AnalyticsEvent.created_at >= since)
            .where(AnalyticsEvent.event_type == EventType.PAGE_LEAVE)
            .where(AnalyticsEvent.path.in_(paths))
            .where(AnalyticsEvent.duration_ms.isnot(None))
            .group_by(AnalyticsEvent.path)
        )
        for dr in (await db.execute(dur_q)).fetchall():
            avg_dur[dr.path] = float(dr.avg_dur) if dr.avg_dur is not None else None

    return [
        TopPage(
            path=r.path,
            views=r.views,
            unique_sessions=r.unique_sessions,
            avg_duration_ms=avg_dur.get(r.path),
        )
        for r in rows
    ]


async def get_user_activity(
    db: AsyncSession, days: int = 7, limit: int = 50
) -> list[UserActivityRow]:
    from app.auth.models import User

    since = _days_ago(days)
    q = (
        select(
            AnalyticsEvent.user_id,
            User.email,
            func.count().label("page_views"),
            func.count(distinct(AnalyticsEvent.session_id)).label("sessions"),
            func.max(AnalyticsEvent.created_at).label("last_seen"),
        )
        .join(User, User.id == AnalyticsEvent.user_id, isouter=True)
        .where(AnalyticsEvent.created_at >= since)
        .where(AnalyticsEvent.user_id.isnot(None))
        .where(AnalyticsEvent.event_type == EventType.PAGE_VIEW)
        .group_by(AnalyticsEvent.user_id, User.email)
        .order_by(func.count().desc())
        .limit(limit)
    )
    rows = (await db.execute(q)).fetchall()
    return [
        UserActivityRow(
            user_id=r.user_id,
            email=r.email,
            page_views=r.page_views,
            sessions=r.sessions,
            last_seen=r.last_seen,
        )
        for r in rows
    ]


async def get_recent_sessions(
    db: AsyncSession, limit: int = 30
) -> list[SessionRow]:
    from app.auth.models import User

    # Get the most recent sessions ordered by last activity
    subq = (
        select(
            AnalyticsEvent.session_id,
            func.max(AnalyticsEvent.created_at).label("last_seen"),
        )
        .group_by(AnalyticsEvent.session_id)
        .order_by(func.max(AnalyticsEvent.created_at).desc())
        .limit(limit)
        .subquery()
    )

    q = (
        select(
            AnalyticsEvent.session_id,
            AnalyticsEvent.user_id,
            User.email,
            AnalyticsEvent.ip_address,
            AnalyticsEvent.user_agent,
            func.count().label("pages_visited"),
            func.min(AnalyticsEvent.created_at).label("first_seen"),
            func.max(AnalyticsEvent.created_at).label("last_seen"),
        )
        .join(subq, subq.c.session_id == AnalyticsEvent.session_id)
        .join(User, User.id == AnalyticsEvent.user_id, isouter=True)
        .where(AnalyticsEvent.event_type == EventType.PAGE_VIEW)
        .group_by(
            AnalyticsEvent.session_id,
            AnalyticsEvent.user_id,
            User.email,
            AnalyticsEvent.ip_address,
            AnalyticsEvent.user_agent,
        )
        .order_by(func.max(AnalyticsEvent.created_at).desc())
    )
    rows = (await db.execute(q)).fetchall()
    return [
        SessionRow(
            session_id=r.session_id,
            user_id=r.user_id,
            email=r.email,
            ip_address=r.ip_address,
            user_agent=r.user_agent,
            pages_visited=r.pages_visited,
            first_seen=r.first_seen,
            last_seen=r.last_seen,
        )
        for r in rows
    ]


async def get_daily_trend(db: AsyncSession, days: int = 30) -> list[DailyCount]:
    since = _days_ago(days)
    q = text(
        """
        SELECT
            DATE(created_at AT TIME ZONE 'UTC') AS day,
            COUNT(*) FILTER (WHERE event_type = 'PAGE_VIEW') AS page_views,
            COUNT(DISTINCT session_id) AS unique_sessions
        FROM analytics_events
        WHERE created_at >= :since
        GROUP BY day
        ORDER BY day
        """
    )
    rows = (await db.execute(q, {"since": since})).fetchall()
    return [
        DailyCount(
            date=str(r.day),
            page_views=r.page_views,
            unique_sessions=r.unique_sessions,
        )
        for r in rows
    ]
