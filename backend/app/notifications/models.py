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
    DEAL_SELL_ON = "DEAL_SELL_ON"
    DEAL_AGENT_INVITED = "DEAL_AGENT_INVITED"
    PLAYER_AVAILABLE = "PLAYER_AVAILABLE"
    SYSTEM_BROADCAST = "SYSTEM_BROADCAST"


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
    """A row here means the user has DISABLED that notification type.
    Absence of a row means the type is enabled (default on).
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
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
