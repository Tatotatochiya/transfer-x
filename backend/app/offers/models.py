import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import JSON, DateTime, Date, ForeignKey, Integer, Numeric, String, Text, Uuid, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class OfferStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    SENT = "SENT"
    COUNTERED = "COUNTERED"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    WITHDRAWN = "WITHDRAWN"
    EXPIRED = "EXPIRED"


class OfferEventType(str, enum.Enum):
    CREATED = "CREATED"
    SENT = "SENT"
    COUNTERED = "COUNTERED"
    IMPROVED = "IMPROVED"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    WITHDRAWN = "WITHDRAWN"
    EXPIRED = "EXPIRED"
    MESSAGE = "MESSAGE"


class Offer(Base):
    __tablename__ = "offers"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    player_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("players.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sale_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("sales.id", ondelete="SET NULL"), nullable=True, index=True
    )
    from_club_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    to_club_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("clubs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    fee_amount: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    wage_weekly: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    contract_years: Mapped[int | None] = mapped_column(Integer, nullable=True)
    contract_end_date: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    add_ons: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[OfferStatus] = mapped_column(
        SAEnum(OfferStatus, name="offerstatus"),
        nullable=False,
        default=OfferStatus.DRAFT,
        index=True,
    )
    # reserved_transfer_amount tracks what has been reserved in buyer's budget
    reserved_transfer_amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), nullable=False, default=Decimal("0")
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    last_actor_club_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("clubs.id", ondelete="SET NULL"), nullable=True
    )
    last_action_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    player: Mapped["app.players.models.Player"] = relationship(  # type: ignore[name-defined]
        "Player", foreign_keys=[player_id]
    )
    sale: Mapped["app.sales.models.Sale | None"] = relationship(  # type: ignore[name-defined]
        "Sale", foreign_keys=[sale_id]
    )
    from_club: Mapped["app.clubs.models.Club"] = relationship(  # type: ignore[name-defined]
        "Club", foreign_keys=[from_club_id]
    )
    to_club: Mapped["app.clubs.models.Club | None"] = relationship(  # type: ignore[name-defined]
        "Club", foreign_keys=[to_club_id]
    )
    messages: Mapped[list["OfferMessage"]] = relationship(
        "OfferMessage", back_populates="offer", cascade="all, delete-orphan", order_by="OfferMessage.created_at"
    )
    events: Mapped[list["OfferEvent"]] = relationship(
        "OfferEvent", back_populates="offer", cascade="all, delete-orphan", order_by="OfferEvent.created_at"
    )


class OfferMessage(Base):
    __tablename__ = "offer_messages"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    offer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("offers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sender_club_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("clubs.id", ondelete="SET NULL"), nullable=True
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    offer: Mapped["Offer"] = relationship("Offer", back_populates="messages")
    sender_club: Mapped["app.clubs.models.Club | None"] = relationship(  # type: ignore[name-defined]
        "Club", foreign_keys=[sender_club_id]
    )


class OfferEvent(Base):
    __tablename__ = "offer_events"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    offer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("offers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_type: Mapped[OfferEventType] = mapped_column(
        SAEnum(OfferEventType, name="offereventtype"), nullable=False, index=True
    )
    actor_club_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("clubs.id", ondelete="SET NULL"), nullable=True
    )
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    offer: Mapped["Offer"] = relationship("Offer", back_populates="events")
