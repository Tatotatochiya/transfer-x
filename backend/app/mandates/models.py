import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import JSON, Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, Uuid, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class MandateStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"


class ClientStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    SEEKING_MOVE = "SEEKING_MOVE"
    LOAN_AVAILABLE = "LOAN_AVAILABLE"
    CONTRACT_EXTENSION = "CONTRACT_EXTENSION"
    UNAVAILABLE = "UNAVAILABLE"


class Mandate(Base):
    __tablename__ = "mandates"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("agent_profiles.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    player_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("players.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    exclusive: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    territory: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status: Mapped[MandateStatus] = mapped_column(
        SAEnum(MandateStatus, name="mandatestatus"),
        nullable=False,
        default=MandateStatus.ACTIVE,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    # Agent-private client profile fields
    client_status: Mapped[ClientStatus] = mapped_column(
        SAEnum(ClientStatus, name="clientstatus"),
        nullable=False,
        default=ClientStatus.ACTIVE,
        server_default="ACTIVE",
    )
    agent_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    preferred_destinations: Mapped[str | None] = mapped_column(Text, nullable=True)
    asking_price: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    asking_wage: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)

    # TRA-134: per-client alert configuration (agent-private, mirrors the fields above)
    alert_contract_expiry_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    alert_contract_expiry_months: Mapped[int] = mapped_column(Integer, nullable=False, default=12, server_default="12")
    alert_valuation_change_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    alert_valuation_change_pct: Mapped[Decimal] = mapped_column(
        Numeric(5, 4), nullable=False, default=Decimal("0.10"), server_default="0.10"
    )
    alert_club_interest_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    # Baselines used to detect "changed since last check" — updated whenever an alert fires
    last_seen_market_value: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    last_seen_interest_club_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    alerts: Mapped[list["ClientAlert"]] = relationship(
        "ClientAlert", back_populates="mandate", cascade="all, delete-orphan", order_by="ClientAlert.created_at.desc()"
    )


class AlertType(str, enum.Enum):
    CONTRACT_EXPIRY = "CONTRACT_EXPIRY"
    VALUATION_CHANGE = "VALUATION_CHANGE"
    CLUB_INTEREST = "CLUB_INTEREST"


class AlertSeverity(str, enum.Enum):
    RED = "RED"
    AMBER = "AMBER"
    GREEN = "GREEN"


class ClientAlert(Base):
    """TRA-134 — a leverage-moment alert for one of an agent's clients."""
    __tablename__ = "client_alerts"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    mandate_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("mandates.id", ondelete="CASCADE"), nullable=False, index=True
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("agent_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    player_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("players.id", ondelete="CASCADE"), nullable=False, index=True
    )
    alert_type: Mapped[AlertType] = mapped_column(SAEnum(AlertType, name="alerttype"), nullable=False, index=True)
    severity: Mapped[AlertSeverity] = mapped_column(SAEnum(AlertSeverity, name="alertseverity"), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    context: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    mandate: Mapped["Mandate"] = relationship("Mandate", back_populates="alerts")
