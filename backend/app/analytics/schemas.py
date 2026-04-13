"""Pydantic schemas for analytics ingest and admin reporting."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.analytics.models import EventType


# ── Ingest ────────────────────────────────────────────────────────────────────


class AnalyticsEventIn(BaseModel):
    session_id: uuid.UUID
    event_type: EventType
    path: str = Field(max_length=512)
    referrer: str | None = Field(default=None, max_length=512)
    element: str | None = Field(default=None, max_length=256)
    duration_ms: int | None = None
    meta: dict | None = None


class AnalyticsEventBatch(BaseModel):
    events: list[AnalyticsEventIn] = Field(min_length=1, max_length=50)


# ── Admin reporting ───────────────────────────────────────────────────────────


class AnalyticsOverview(BaseModel):
    total_events_today: int
    total_events_7d: int
    total_events_30d: int
    unique_sessions_today: int
    unique_sessions_7d: int
    dau_today: int       # distinct user_ids with a session today
    dau_7d: int          # avg daily active users over last 7 days
    page_views_today: int
    page_views_7d: int


class TopPage(BaseModel):
    path: str
    views: int
    unique_sessions: int
    avg_duration_ms: float | None


class UserActivityRow(BaseModel):
    user_id: uuid.UUID
    email: str | None
    page_views: int
    sessions: int
    last_seen: datetime


class SessionRow(BaseModel):
    session_id: uuid.UUID
    user_id: uuid.UUID | None
    email: str | None
    ip_address: str | None
    user_agent: str | None
    pages_visited: int
    first_seen: datetime
    last_seen: datetime


class DailyCount(BaseModel):
    date: str   # ISO date string YYYY-MM-DD
    page_views: int
    unique_sessions: int
