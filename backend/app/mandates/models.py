import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Numeric, String, Text, Uuid, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

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
