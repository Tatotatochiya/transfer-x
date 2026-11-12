"""Move reminders (docs/feature_spec/move-reminders): who chased whom, when."""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class MoveReminder(Base):
    __tablename__ = "move_reminders"
    __table_args__ = (Index("ix_move_reminders_subject", "subject_type", "subject_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # "offer", "deal" or "enquiry".
    subject_type: Mapped[str] = mapped_column(String(20), nullable=False)
    subject_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    # What was being waited for, e.g. "deal:AGENT_NEGOTIATION:propose-commission".
    move_key: Mapped[str] = mapped_column(String(80), nullable=False)
    # "club", "agent" or "player", and that club's, agent profile's or player's id.
    holder_kind: Mapped[str] = mapped_column(String(10), nullable=False)
    holder_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    # Null for an automatic reminder (sent by TransferX).
    sender_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    # The club that sent it; null for an agent or TransferX.
    sender_club_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    escalated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    automatic: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    note: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
