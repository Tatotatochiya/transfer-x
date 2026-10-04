import enum
import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, Uuid, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class NotificationType(str, enum.Enum):
    OUTBID = "OUTBID"
    OFFER_RECEIVED = "OFFER_RECEIVED"
    OFFER_ACCEPTED = "OFFER_ACCEPTED"
    OFFER_REJECTED = "OFFER_REJECTED"
    OFFER_COUNTERED = "OFFER_COUNTERED"
    OFFER_WITHDRAWN = "OFFER_WITHDRAWN"
    OFFER_EXPIRING = "OFFER_EXPIRING"
    OFFER_MESSAGE = "OFFER_MESSAGE"
    AUCTION_BID_RECEIVED = "AUCTION_BID_RECEIVED"
    AUCTION_ENDING = "AUCTION_ENDING"
    AUCTION_BID_ACCEPTED = "AUCTION_BID_ACCEPTED"
    DEAL_COMPLETED = "DEAL_COMPLETED"
    DEAL_COLLAPSED = "DEAL_COLLAPSED"
    SALE_REOPENED = "SALE_REOPENED"
    DEAL_SLA_BREACHED = "DEAL_SLA_BREACHED"
    DEAL_SELL_ON = "DEAL_SELL_ON"
    DEAL_AGENT_INVITED = "DEAL_AGENT_INVITED"
    DEAL_PERSONAL_TERMS_SENT = "DEAL_PERSONAL_TERMS_SENT"
    PLAYER_AVAILABLE = "PLAYER_AVAILABLE"
    SYSTEM_BROADCAST = "SYSTEM_BROADCAST"
    VERIFICATION_APPROVED = "VERIFICATION_APPROVED"
    VERIFICATION_REJECTED = "VERIFICATION_REJECTED"
    REPRESENTATION_STARTED = "REPRESENTATION_STARTED"
    REPRESENTATION_REVOKED = "REPRESENTATION_REVOKED"
    REPRESENTATION_EXPIRED = "REPRESENTATION_EXPIRED"
    PERSONAL_TERMS_DECISION = "PERSONAL_TERMS_DECISION"
    INSTALMENT_DUE = "INSTALMENT_DUE"
    DEAL_CLAUSE_TRIGGERED = "DEAL_CLAUSE_TRIGGERED"
    RELEASE_CLAUSE_TRIGGERED = "RELEASE_CLAUSE_TRIGGERED"
    NEGOTIATION_MESSAGE = "NEGOTIATION_MESSAGE"
    CLIENT_ALERT = "CLIENT_ALERT"
    STAFF_INVITATION = "STAFF_INVITATION"
    APPROVAL_REQUESTED = "APPROVAL_REQUESTED"
    APPROVAL_DECIDED = "APPROVAL_DECIDED"
    LOAN_STARTED = "LOAN_STARTED"
    LOAN_ENDING_SOON = "LOAN_ENDING_SOON"
    LOAN_ENDED = "LOAN_ENDED"
    LOAN_RECALLED = "LOAN_RECALLED"
    LOAN_CONVERTED = "LOAN_CONVERTED"
    # Preference only: switches the daily "waiting on you" email on or off.
    # No in-app notification is created with it (notifications/digest.py).
    DAILY_DIGEST = "DAILY_DIGEST"
    DEAL_PAPERWORK = "DEAL_PAPERWORK"
    ENQUIRY_RECEIVED = "ENQUIRY_RECEIVED"
    ENQUIRY_REPLIED = "ENQUIRY_REPLIED"
    # A colleague asked from Lite ("Ask Sam", lite-mode BACKEND §6).
    LITE_QUESTION = "LITE_QUESTION"


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recipient_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    type: Mapped[NotificationType] = mapped_column(
        SAEnum(NotificationType, name="notificationtype"), nullable=False, index=True
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)
    link: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    related_player_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("players.id", ondelete="SET NULL"), nullable=True
    )
    related_club_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("clubs.id", ondelete="SET NULL"), nullable=True
    )
    # Web Push (migration 0088, docs/feature_spec/mobile-notifications). The
    # push shows `title` (falling back to `message`) and `body`. `group_key`
    # names the subject ("offer:{id}", "sale:{id}", "deal:{id}"…): it is the
    # push tag, so a newer push about the same subject replaces the older one,
    # and the scheduled reminders use it to tell each person only once.
    title: Mapped[str | None] = mapped_column(String(120), nullable=True)
    body: Mapped[str | None] = mapped_column(String(240), nullable=True)
    group_key: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    deadline_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Up to two {action, title, url}. They only ever open a page (ADR 0006).
    actions_json: Mapped[list | None] = mapped_column(JSON().with_variant(JSONB, "postgresql"), nullable=True)
    # Phase 4 email fallback (migration 0091): with a phone to push to, a
    # "your move" email waits until this time and goes only if still unread.
    email_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    emailed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    recipient: Mapped["app.auth.models.User"] = relationship(  # type: ignore[name-defined]
        "User", foreign_keys=[recipient_user_id]
    )


class NotificationPreference(Base):
    """Per-user, per-type channel preferences.
    Absence of a row means both channels are enabled (default on).
    """

    __tablename__ = "notification_preferences"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    type: Mapped[NotificationType] = mapped_column(
        SAEnum(NotificationType, name="notificationtype"),
        primary_key=True,
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    # TRA-44: independent email opt-out — only meaningful while `enabled` is True.
    email_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    push_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


# ── Web Push (migration 0088) ─────────────────────────────────────────────────


class PushPlatform(str, enum.Enum):
    IOS_HOME_SCREEN = "IOS_HOME_SCREEN"
    ANDROID = "ANDROID"
    DESKTOP = "DESKTOP"
    OTHER = "OTHER"


class PushDeliveryStatus(str, enum.Enum):
    SENT = "SENT"
    HELD = "HELD"                            # quiet hours: sent once send_after passes
    SKIPPED_DUPLICATE = "SKIPPED_DUPLICATE"  # the same subject was pushed recently
    SKIPPED = "SKIPPED"                      # held, but read before it was released
    FAILED = "FAILED"


class PushSubscription(Base):
    """One browser or Home Screen app that has said yes to notifications."""

    __tablename__ = "push_subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    endpoint: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    p256dh: Mapped[str] = mapped_column(String(200), nullable=False)
    auth: Mapped[str] = mapped_column(String(200), nullable=False)
    platform: Mapped[PushPlatform] = mapped_column(
        SAEnum(PushPlatform, name="pushplatform"), nullable=False, default=PushPlatform.OTHER, server_default="OTHER"
    )
    user_agent: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_failure_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")


class PushDelivery(Base):
    """What was decided for one notification and one person: sent, held for
    quiet hours, skipped as a repeat, or failed. Also the record of when a
    push was opened."""

    __tablename__ = "push_deliveries"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    notification_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("notifications.id", ondelete="CASCADE"), nullable=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[NotificationType | None] = mapped_column(SAEnum(NotificationType, name="notificationtype"), nullable=True)
    group_key: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[PushDeliveryStatus] = mapped_column(
        SAEnum(PushDeliveryStatus, name="pushdeliverystatus"), nullable=False
    )
    send_after: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
