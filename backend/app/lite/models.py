"""Lite mode (docs/feature_spec/lite-mode): per-user preferences."""
import enum
import uuid
from datetime import datetime, time

from sqlalchemy import JSON, Boolean, DateTime, Enum as SAEnum, ForeignKey, String, Text, Time, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class TextScale(str, enum.Enum):
    NORMAL = "NORMAL"   # 100%
    LARGE = "LARGE"     # 112.5%
    LARGER = "LARGER"   # 125%


class PushMode(str, enum.Enum):
    """How a notification tier arrives on a phone (mobile notifications §4)."""
    SOUND = "SOUND"
    SILENT = "SILENT"
    OFF = "OFF"


class UserPreference(Base):
    """Settings that follow a person across devices (migration 0085).

    `lite_mode` null means "use the default": on for owners and sporting
    directors once Lite is complete (settings.lite_role_default_on), off for
    everyone else. The text scale applies inside Lite only (product decision,
    2026-09-29): the full app uses fixed pixel sizes that would not scale.
    """
    __tablename__ = "user_preferences"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    lite_mode: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    text_scale: Mapped[TextScale] = mapped_column(
        SAEnum(TextScale, name="textscale"), nullable=False, default=TextScale.NORMAL, server_default="NORMAL"
    )
    # The last unfinished Lite flow, for "Carry on where you left off" (L2).
    lite_resume_json: Mapped[dict | None] = mapped_column(JSON().with_variant(JSONB, "postgresql"), nullable=True)
    # Mobile notifications (migration 0088, docs/feature_spec/mobile-notifications §4).
    push_your_move: Mapped[PushMode] = mapped_column(
        SAEnum(PushMode, name="pushmode"), nullable=False, default=PushMode.SOUND, server_default="SOUND"
    )
    push_heads_up: Mapped[PushMode] = mapped_column(
        SAEnum(PushMode, name="pushmode"), nullable=False, default=PushMode.SILENT, server_default="SILENT"
    )
    push_summary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    summary_local_time: Mapped[time] = mapped_column(Time, nullable=False, default=time(8, 0), server_default="08:00")
    quiet_hours_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    quiet_start: Mapped[time] = mapped_column(Time, nullable=False, default=time(22, 0), server_default="22:00")
    quiet_end: Mapped[time] = mapped_column(Time, nullable=False, default=time(7, 0), server_default="07:00")
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="Europe/London", server_default="Europe/London")
    # Review decision 1: the lock screen shows what happened, never the figures.
    push_hide_amounts: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )



# ── Held sends for undo (L6, architecture ADR 0007) ───────────────────────────


class HeldActionStatus(str, enum.Enum):
    HELD = "HELD"            # waiting out the undo window; nothing sent yet
    EXECUTED = "EXECUTED"    # sent through the normal endpoint
    CANCELLED = "CANCELLED"  # undone in time: the other club never knew
    FAILED = "FAILED"        # the endpoint refused it when its time came


class HeldActionChannel(str, enum.Enum):
    APP = "APP"
    EMAIL = "EMAIL"  # L8 (decisions from email)


class HeldAction(Base):
    """A confirmed Lite action that waits `execute_at` (10 seconds) before it
    is sent, so it can be undone with no trace for the other club.

    Created by the user's confirm, never by the assistant (ADR 0006). While
    HELD there are no notifications, emails or websocket events: the action
    hasn't happened. The executor (main.py, every 2 seconds) then runs the
    normal endpoint as the user who confirmed it."""
    __tablename__ = "held_actions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    club_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("clubs.id", ondelete="CASCADE"), nullable=True
    )
    kind: Mapped[str] = mapped_column(String(20), nullable=False)  # bid | counter | accept | reject
    payload_json: Mapped[dict] = mapped_column(JSON().with_variant(JSONB, "postgresql"), nullable=False)
    status: Mapped[HeldActionStatus] = mapped_column(
        SAEnum(HeldActionStatus, name="heldactionstatus"), nullable=False, default=HeldActionStatus.HELD, index=True
    )
    execute_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    result_json: Mapped[dict | None] = mapped_column(JSON().with_variant(JSONB, "postgresql"), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    channel: Mapped[HeldActionChannel] = mapped_column(
        SAEnum(HeldActionChannel, name="heldactionchannel"), nullable=False, default=HeldActionChannel.APP,
        server_default="APP",
    )
    ai_assisted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
