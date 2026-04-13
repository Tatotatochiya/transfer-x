"""Analytics event model — stores page views, page leaves, and click events."""

import enum
import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class EventType(str, enum.Enum):
    PAGE_VIEW = "PAGE_VIEW"
    PAGE_LEAVE = "PAGE_LEAVE"
    CLICK = "CLICK"


class AnalyticsEvent(Base):
    __tablename__ = "analytics_events"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(sa.Uuid(as_uuid=True), nullable=False, index=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    ip_address: Mapped[str | None] = mapped_column(sa.String(45), nullable=True)  # IPv4 or IPv6
    user_agent: Mapped[str | None] = mapped_column(sa.String(512), nullable=True)
    event_type: Mapped[EventType] = mapped_column(sa.Enum(EventType, name="analytics_event_type"), nullable=False, index=True)
    path: Mapped[str] = mapped_column(sa.String(512), nullable=False, index=True)
    referrer: Mapped[str | None] = mapped_column(sa.String(512), nullable=True)
    element: Mapped[str | None] = mapped_column(sa.String(256), nullable=True)  # for CLICK events
    duration_ms: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)  # for PAGE_LEAVE events
    meta: Mapped[dict | None] = mapped_column(sa.JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False, index=True
    )
