import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Uuid, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class InvitationStatus(str, enum.Enum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    DECLINED = "DECLINED"


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
