"""When each person last read a transfer's conversation (migration 0110)."""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ConversationRead(Base):
    """One row per person per transfer conversation: the player and the
    buying club identify it (ADR 0008: one conversation per transfer, across
    its enquiry, offers and deal). Messages from others after `read_at` are
    unread for that person. Per person, not per club: a colleague reading it
    doesn't mean you have."""
    __tablename__ = "conversation_reads"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    player_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("players.id", ondelete="CASCADE"), primary_key=True
    )
    buyer_club_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("clubs.id", ondelete="CASCADE"), primary_key=True
    )
    read_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
