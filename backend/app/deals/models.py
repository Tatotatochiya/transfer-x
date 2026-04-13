import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, Uuid, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class DealStatus(str, enum.Enum):
    IN_PROGRESS = "IN_PROGRESS"
    PENDING_COMPLETION = "PENDING_COMPLETION"
    COMPLETED = "COMPLETED"
    COLLAPSED = "COLLAPSED"


class DealStage(str, enum.Enum):
    AGREEMENT = "AGREEMENT"
    PAPERWORK = "PAPERWORK"
    CONFIRMED = "CONFIRMED"
    COMPLETED = "COMPLETED"


class Deal(Base):
    __tablename__ = "deals"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sale_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("sales.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    bid_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("bids.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    offer_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("offers.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    buyer_club_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("clubs.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    seller_club_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("clubs.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    player_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("players.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    agreed_fee: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    agreed_wage_weekly: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    status: Mapped[DealStatus] = mapped_column(
        SAEnum(DealStatus, name="dealstatus"),
        nullable=False,
        default=DealStatus.IN_PROGRESS,
        index=True,
    )
    stage: Mapped[DealStage] = mapped_column(
        SAEnum(DealStage, name="dealstage"),
        nullable=False,
        default=DealStage.AGREEMENT,
        index=True,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    sale: Mapped["app.sales.models.Sale | None"] = relationship(  # type: ignore[name-defined]
        "Sale", foreign_keys=[sale_id]
    )
    offer: Mapped["app.offers.models.Offer | None"] = relationship(  # type: ignore[name-defined]
        "Offer", foreign_keys=[offer_id]
    )
    buyer_club: Mapped["app.clubs.models.Club"] = relationship(  # type: ignore[name-defined]
        "Club", foreign_keys=[buyer_club_id]
    )
    seller_club: Mapped["app.clubs.models.Club | None"] = relationship(  # type: ignore[name-defined]
        "Club", foreign_keys=[seller_club_id]
    )
    player: Mapped["app.players.models.Player"] = relationship(  # type: ignore[name-defined]
        "Player", foreign_keys=[player_id]
    )
    deal_notes: Mapped[list["DealNote"]] = relationship(
        "DealNote", back_populates="deal", cascade="all, delete-orphan", order_by="DealNote.created_at"
    )

    @property
    def is_auction_deal(self) -> bool:
        from app.sales.models import SaleType
        return self.sale_id is not None and (
            self.sale is not None and self.sale.sale_type == SaleType.AUCTION
        )


class DealNote(Base):
    __tablename__ = "deal_notes"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    deal_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("deals.id", ondelete="CASCADE"), nullable=False, index=True
    )
    author_club_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("clubs.id", ondelete="SET NULL"), nullable=True
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    deal: Mapped["Deal"] = relationship("Deal", back_populates="deal_notes")
    author_club: Mapped["app.clubs.models.Club | None"] = relationship(  # type: ignore[name-defined]
        "Club", foreign_keys=[author_club_id]
    )
