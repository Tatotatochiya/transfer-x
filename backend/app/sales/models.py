import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Numeric, String, Text, Uuid, func, text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class SaleType(str, enum.Enum):
    AUCTION = "AUCTION"
    OPEN_TO_OFFERS = "OPEN_TO_OFFERS"
    FIXED_PRICE = "FIXED_PRICE"


class ListingAvailability(str, enum.Enum):
    """What the selling club will consider for this player — separate from
    `SaleType`, which is *how* offers arrive. A loan cannot be auctioned, so
    this is not a fourth sale type."""
    TRANSFER = "TRANSFER"
    LOAN = "LOAN"
    EITHER = "EITHER"


class SaleStatus(str, enum.Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    WITHDRAWN = "WITHDRAWN"
    EXPIRED = "EXPIRED"


class SaleEventType(str, enum.Enum):
    CREATED = "CREATED"
    BID_PLACED = "BID_PLACED"
    BID_REPLACED = "BID_REPLACED"
    BID_ACCEPTED = "BID_ACCEPTED"
    SALE_CLOSED = "SALE_CLOSED"
    SALE_WITHDRAWN = "SALE_WITHDRAWN"
    SALE_EXTENDED = "SALE_EXTENDED"
    SALE_EXPIRED = "SALE_EXPIRED"


class BidStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    WITHDRAWN = "WITHDRAWN"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    OUTBID = "OUTBID"


class Sale(Base):
    __tablename__ = "sales"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    player_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("players.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    seller_club_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("clubs.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    sale_type: Mapped[SaleType] = mapped_column(
        SAEnum(SaleType, name="saletype"), nullable=False, index=True
    )
    availability: Mapped[ListingAvailability] = mapped_column(
        SAEnum(ListingAvailability, name="listingavailability"),
        nullable=False,
        default=ListingAvailability.TRANSFER,
        server_default="TRANSFER",
        index=True,
    )
    asking_price: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    reserve_price: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    min_increment: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), nullable=False, default=Decimal("500000")
    )
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Set when TransferX staff cancelled the listing from the admin panel, so
    # it reads differently from a seller's own withdrawal (migration 0092).
    staff_cancel_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    @property
    def cancelled_by_staff(self) -> bool:
        return self.staff_cancel_reason is not None
    status: Mapped[SaleStatus] = mapped_column(
        SAEnum(SaleStatus, name="salestatus"),
        nullable=False,
        default=SaleStatus.OPEN,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # A player has at most one live listing. The router checks first so the
    # caller gets a readable 409, but a check-then-insert cannot stop two
    # concurrent requests (a fast double-click) from both passing — this index
    # is what actually guarantees it.
    __table_args__ = (
        Index(
            "uq_sales_one_open_per_player",
            "player_id",
            unique=True,
            postgresql_where=text("status = 'OPEN'"),
            sqlite_where=text("status = 'OPEN'"),
        ),
    )

    player: Mapped["app.players.models.Player"] = relationship(  # type: ignore[name-defined]
        "Player", foreign_keys=[player_id]
    )
    seller_club: Mapped["app.clubs.models.Club"] = relationship(  # type: ignore[name-defined]
        "Club", foreign_keys=[seller_club_id]
    )
    bids: Mapped[list["Bid"]] = relationship(
        "Bid", back_populates="sale", cascade="all, delete-orphan"
    )
    events: Mapped[list["SaleEvent"]] = relationship(
        "SaleEvent", back_populates="sale", cascade="all, delete-orphan"
    )


class SaleEvent(Base):
    __tablename__ = "sale_events"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sale_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("sales.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_type: Mapped[SaleEventType] = mapped_column(
        SAEnum(SaleEventType, name="saleeventtype"), nullable=False, index=True
    )
    actor_club_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("clubs.id", ondelete="SET NULL"), nullable=True
    )
    bid_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    sale: Mapped["Sale"] = relationship("Sale", back_populates="events")


class Bid(Base):
    __tablename__ = "bids"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sale_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("sales.id", ondelete="CASCADE"), nullable=False, index=True
    )
    buyer_club_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("clubs.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    wage_offer_weekly: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    status: Mapped[BidStatus] = mapped_column(
        SAEnum(BidStatus, name="bidstatus"),
        nullable=False,
        default=BidStatus.ACTIVE,
        index=True,
    )
    reserved_transfer_amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), nullable=False, default=Decimal("0")
    )
    reserved_wage_weekly: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), nullable=False, default=Decimal("0")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    sale: Mapped["Sale"] = relationship("Sale", back_populates="bids")
    buyer_club: Mapped["app.clubs.models.Club"] = relationship(  # type: ignore[name-defined]
        "Club", foreign_keys=[buyer_club_id]
    )
