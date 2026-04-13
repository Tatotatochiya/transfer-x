"""Analytics router — public ingest endpoint + superuser reporting endpoints."""

import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics import service as analytics_service
from app.analytics.schemas import (
    AnalyticsEventBatch,
    AnalyticsOverview,
    DailyCount,
    SessionRow,
    TopPage,
    UserActivityRow,
)
from app.database import get_db
from app.deps import get_current_superuser, get_optional_user
from app.auth.models import User

router = APIRouter(tags=["analytics"])


def _get_client_ip(request: Request) -> str | None:
    """Extract real client IP, respecting X-Forwarded-For from reverse proxies."""
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else None


# ── Ingest (no auth required — fire-and-forget from client) ──────────────────


@router.post("/analytics/events", status_code=204)
async def ingest_events(
    body: AnalyticsEventBatch,
    request: Request,
    current_user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    ip = _get_client_ip(request)
    ua = request.headers.get("User-Agent", "")[:512]
    user_id = current_user.id if current_user else None
    await analytics_service.record_events(db, body.events, user_id=user_id, ip_address=ip, user_agent=ua)
    await db.commit()


# ── Admin reporting (superuser only) ─────────────────────────────────────────


@router.get("/analytics/overview", response_model=AnalyticsOverview)
async def analytics_overview(
    _: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
) -> AnalyticsOverview:
    return await analytics_service.get_overview(db)


@router.get("/analytics/pages", response_model=list[TopPage])
async def analytics_top_pages(
    days: int = Query(7, ge=1, le=90),
    limit: int = Query(20, ge=1, le=100),
    _: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
) -> list[TopPage]:
    return await analytics_service.get_top_pages(db, days=days, limit=limit)


@router.get("/analytics/users", response_model=list[UserActivityRow])
async def analytics_user_activity(
    days: int = Query(7, ge=1, le=90),
    limit: int = Query(50, ge=1, le=200),
    _: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
) -> list[UserActivityRow]:
    return await analytics_service.get_user_activity(db, days=days, limit=limit)


@router.get("/analytics/sessions", response_model=list[SessionRow])
async def analytics_sessions(
    limit: int = Query(30, ge=1, le=200),
    _: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
) -> list[SessionRow]:
    return await analytics_service.get_recent_sessions(db, limit=limit)


@router.get("/analytics/trend", response_model=list[DailyCount])
async def analytics_daily_trend(
    days: int = Query(30, ge=7, le=90),
    _: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
) -> list[DailyCount]:
    return await analytics_service.get_daily_trend(db, days=days)
