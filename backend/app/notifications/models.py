import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, Uuid, func
from sqlalchemy import Enum as SAEnum
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
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
