"""Enquiries — "is he available, and what would it take?" (migration 0080).

A real transfer rarely opens with a formal offer. A club asks first, and only
then makes an offer — which on TransferX reserves budget, may need spending
approval, and starts a clock. An enquiry is the lighter first step: a thread
between the asking club and the club that owns the player, optionally without
naming the asking club, that commits nobody to anything and can turn into an
offer when both sides are ready.
"""
import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, Uuid, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class EnquiryStatus(str, enum.Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"


class Enquiry(Base):
    __tablename__ = "enquiries"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    player_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("players.id", ondelete="CASCADE"), nullable=False, index=True
    )
    from_club_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    to_club_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Masked from the owning club, as an anonymous offer is (ADR 0004).
    is_anonymous: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    status: Mapped[EnquiryStatus] = mapped_column(
        SAEnum(EnquiryStatus, name="enquirystatus"), nullable=False, default=EnquiryStatus.OPEN, index=True
    )
    # Whoever wrote last; the other club is the one with the next move.
    last_actor_club_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    player: Mapped["app.players.models.Player"] = relationship("Player")  # type: ignore[name-defined]
    from_club: Mapped["app.clubs.models.Club"] = relationship("Club", foreign_keys=[from_club_id])  # type: ignore[name-defined]
    to_club: Mapped["app.clubs.models.Club"] = relationship("Club", foreign_keys=[to_club_id])  # type: ignore[name-defined]
    messages: Mapped[list["EnquiryMessage"]] = relationship(
        "EnquiryMessage", order_by="EnquiryMessage.created_at", cascade="all, delete-orphan"
    )


class EnquiryMessage(Base):
    __tablename__ = "enquiry_messages"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    enquiry_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("enquiries.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sender_club_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
