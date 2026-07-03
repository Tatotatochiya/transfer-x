import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, Uuid, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class InvitationStatus(str, enum.Enum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    DECLINED = "DECLINED"


class NegotiationStatus(str, enum.Enum):
    IN_PROGRESS = "IN_PROGRESS"
    TERMS_AGREED = "TERMS_AGREED"
    COLLAPSED = "COLLAPSED"


class AgreementStatus(str, enum.Enum):
    PENDING = "PENDING"
    AGREED = "AGREED"
    DECLINED = "DECLINED"


class CommissionPayer(str, enum.Enum):
    BUYER = "BUYER"
    SELLER = "SELLER"
    PLAYER = "PLAYER"


class AgentDealInvitation(Base):
    __tablename__ = "agent_deal_invitations"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    deal_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("deals.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("agent_profiles.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    status: Mapped[InvitationStatus] = mapped_column(
        SAEnum(InvitationStatus, name="invitationstatus"),
        nullable=False,
        default=InvitationStatus.PENDING,
        server_default="PENDING",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    deal: Mapped["app.deals.models.Deal"] = relationship(  # type: ignore[name-defined]
        "Deal", foreign_keys=[deal_id]
    )
    agent: Mapped["app.auth.models.AgentProfile"] = relationship(  # type: ignore[name-defined]
        "AgentProfile", foreign_keys=[agent_id]
    )


class AgentNegotiation(Base):
    """Three-way negotiation record created when a deal enters AGENT_NEGOTIATION stage (TRA-127).

    The agent proposes club-side commission terms and player-side personal terms.
    Both parties must reach AGREED before the deal can advance.
    """
    __tablename__ = "agent_negotiations"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    deal_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("deals.id", ondelete="CASCADE"),
        nullable=False, unique=True, index=True,
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("agent_profiles.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    status: Mapped[NegotiationStatus] = mapped_column(
        SAEnum(NegotiationStatus, name="negotiationstatus"),
        nullable=False,
        default=NegotiationStatus.IN_PROGRESS,
        server_default="IN_PROGRESS",
    )
    # Club-side terms (commission proposal to buying club)
    commission_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    commission_amount: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    commission_payer: Mapped[CommissionPayer | None] = mapped_column(
        SAEnum(CommissionPayer, name="commissionpayer"), nullable=True
    )
    additional_conditions: Mapped[str | None] = mapped_column(Text, nullable=True)
    club_agreement: Mapped[AgreementStatus] = mapped_column(
        SAEnum(AgreementStatus, name="agreementstatus"),
        nullable=False,
        default=AgreementStatus.PENDING,
        server_default="PENDING",
    )
    # Player-side terms (personal terms proposed to player)
    proposed_wage_weekly: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    proposed_signing_bonus: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    proposed_length_years: Mapped[int | None] = mapped_column(Integer, nullable=True)
    player_agreement: Mapped[AgreementStatus] = mapped_column(
        SAEnum(AgreementStatus, name="agreementstatus"),
        nullable=False,
        default=AgreementStatus.PENDING,
        server_default="PENDING",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    agreed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    deal: Mapped["app.deals.models.Deal"] = relationship(  # type: ignore[name-defined]
        "Deal", foreign_keys=[deal_id]
    )
    agent: Mapped["app.auth.models.AgentProfile"] = relationship(  # type: ignore[name-defined]
        "AgentProfile", foreign_keys=[agent_id]
    )


class CommissionStatus(str, enum.Enum):
    PENDING   = "PENDING"    # Terms agreed; deal not yet complete
    CONFIRMED = "CONFIRMED"  # Deal completed; commission due
    INVOICED  = "INVOICED"   # Agent has raised invoice
    PAID      = "PAID"       # Commission paid


class AgentCommission(Base):
    """Per-deal commission record derived from AgentNegotiation (TRA-132)."""
    __tablename__ = "agent_commissions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    deal_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("deals.id", ondelete="CASCADE"),
        nullable=False, unique=True, index=True,
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("agent_profiles.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    window_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("transfer_windows.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    payer: Mapped[CommissionPayer | None] = mapped_column(
        SAEnum(CommissionPayer, name="commissionpayer"), nullable=True
    )
    status: Mapped[CommissionStatus] = mapped_column(
        SAEnum(CommissionStatus, name="commissionstatus"),
        nullable=False,
        default=CommissionStatus.PENDING,
        server_default="PENDING",
    )
    window_label: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    invoiced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    deal: Mapped["app.deals.models.Deal"] = relationship(  # type: ignore[name-defined]
        "Deal", foreign_keys=[deal_id]
    )
    agent: Mapped["app.auth.models.AgentProfile"] = relationship(  # type: ignore[name-defined]
        "AgentProfile", foreign_keys=[agent_id]
    )


class NegotiationThread(str, enum.Enum):
    CLUB_SIDE = "CLUB_SIDE"
    PLAYER_SIDE = "PLAYER_SIDE"


class NegotiationMessage(Base):
    """Scoped negotiation thread message (TRA-136).

    Immutable (no edit/delete in v1) — the thread doubles as a negotiation
    record. Visibility is enforced server-side in the service/router layer,
    never by the frontend: the agent sees both threads, the club sees only
    CLUB_SIDE, the player sees only PLAYER_SIDE.
    """
    __tablename__ = "negotiation_messages"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    negotiation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("agent_negotiations.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    thread: Mapped[NegotiationThread] = mapped_column(
        SAEnum(NegotiationThread, name="negotiationthread"), nullable=False, index=True
    )
    sender_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    negotiation: Mapped["AgentNegotiation"] = relationship("AgentNegotiation", foreign_keys=[negotiation_id])
    sender: Mapped["app.auth.models.User | None"] = relationship(  # type: ignore[name-defined]
        "User", foreign_keys=[sender_user_id]
    )
