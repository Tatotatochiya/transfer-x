import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, Uuid, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class VerificationEntityType(str, enum.Enum):
    CLUB = "CLUB"
    AGENT = "AGENT"
    PLAYER = "PLAYER"


class VerificationStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class VerificationRequest(Base):
    """A request from an actor to be verified, reviewed by an admin (TRA-89)."""
    __tablename__ = "verification_requests"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_type: Mapped[VerificationEntityType] = mapped_column(
        SAEnum(VerificationEntityType, name="verificationentitytype"), nullable=False, index=True
    )
    # Club.id / AgentProfile.id / PlayerProfile.id depending on entity_type — no FK since it's polymorphic.
    entity_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    requested_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[VerificationStatus] = mapped_column(
        SAEnum(VerificationStatus, name="verificationstatus"),
        nullable=False,
        default=VerificationStatus.PENDING,
        server_default="PENDING",
        index=True,
    )
    evidence_ref: Mapped[str | None] = mapped_column(String(500), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    requested_by: Mapped["app.auth.models.User | None"] = relationship(  # type: ignore[name-defined]
        "User", foreign_keys=[requested_by_user_id]
    )
    reviewed_by: Mapped["app.auth.models.User | None"] = relationship(  # type: ignore[name-defined]
        "User", foreign_keys=[reviewed_by_user_id]
    )
