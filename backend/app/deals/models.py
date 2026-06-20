import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, Uuid, func
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
    AGENT_NEGOTIATION = "AGENT_NEGOTIATION"  # TRA-125/127: inserted when player has active mandate
    PERSONAL_TERMS = "PERSONAL_TERMS"        # TRA-60: player consents to wage/contract terms
    PAPERWORK = "PAPERWORK"
    CONFIRMED = "CONFIRMED"
    COMPLETED = "COMPLETED"


class DealType(str, enum.Enum):
    PERMANENT = "PERMANENT"
    LOAN = "LOAN"


class ClauseType(str, enum.Enum):
    APPEARANCES = "APPEARANCES"
    GOALS = "GOALS"
    PROMOTION = "PROMOTION"
    RESALE = "RESALE"
    OTHER = "OTHER"


class ClauseStatus(str, enum.Enum):
    PENDING = "PENDING"
    TRIGGERED = "TRIGGERED"
    PAID = "PAID"


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
    # TRA-56: loan fields
    deal_type: Mapped[DealType] = mapped_column(
        SAEnum(DealType, name="dealtype"),
        nullable=False,
        default=DealType.PERMANENT,
        server_default="PERMANENT",
    )
    loan_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    loan_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    loan_fee: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    option_to_buy: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    obligation_to_buy: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    obligation_conditions: Mapped[str | None] = mapped_column(Text, nullable=True)
    # TRA-57: sell-on percentage (0.0–1.0), recorded on the selling club's side
    sell_on_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
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
    clauses: Mapped[list["DealClause"]] = relationship(
        "DealClause", back_populates="deal", cascade="all, delete-orphan"
    )
    instalments: Mapped[list["DealInstalment"]] = relationship(
        "DealInstalment", back_populates="deal", cascade="all, delete-orphan",
        order_by="DealInstalment.due_date",
    )
    personal_terms: Mapped["PersonalTerms | None"] = relationship(
        "PersonalTerms", back_populates="deal", uselist=False, cascade="all, delete-orphan"
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


class DealClause(Base):
    __tablename__ = "deal_clauses"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    deal_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("deals.id", ondelete="CASCADE"), nullable=False, index=True
    )
    clause_type: Mapped[ClauseType] = mapped_column(
        SAEnum(ClauseType, name="clausetype"), nullable=False
    )
    trigger_description: Mapped[str] = mapped_column(Text, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    cap: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    status: Mapped[ClauseStatus] = mapped_column(
        SAEnum(ClauseStatus, name="clausestatus"),
        nullable=False,
        default=ClauseStatus.PENDING,
        server_default="PENDING",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    deal: Mapped["Deal"] = relationship("Deal", back_populates="clauses")


class DealInstalment(Base):
    __tablename__ = "deal_instalments"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    deal_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("deals.id", ondelete="CASCADE"), nullable=False, index=True
    )
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    paid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    deal: Mapped["Deal"] = relationship("Deal", back_populates="instalments")


class PersonalTerms(Base):
    """Player personal terms proposed during PERSONAL_TERMS stage (TRA-60).

    Player (or agent on their behalf) must set player_consent = AGREED before the deal
    can advance to PAPERWORK. DECLINED collapses the deal.
    """
    __tablename__ = "personal_terms"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    deal_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("deals.id", ondelete="CASCADE"),
        nullable=False, unique=True, index=True,
    )
    # The agent who drafted these terms (FK to agent_profiles; nullable if no agent involved)
    agent_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("agent_profiles.id", ondelete="SET NULL"), nullable=True
    )
    wage_weekly: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    signing_bonus: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    length_years: Mapped[int | None] = mapped_column(Integer, nullable=True)
    player_consent: Mapped["app.agents.models.AgreementStatus"] = mapped_column(  # type: ignore[name-defined]
        SAEnum("PENDING", "AGREED", "DECLINED", name="agreementstatus"),
        nullable=False,
        server_default="PENDING",
    )
    agreed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    deal: Mapped["Deal"] = relationship("Deal", back_populates="personal_terms")
