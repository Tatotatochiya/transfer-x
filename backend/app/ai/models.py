"""AI assistant records (migration 0086).

`AISuggestionEvent`: each time the assistant offers something a user can
use (a counter, a guide price, a draft, an action from Ask) it is SHOWN;
using it records USED. Shown without used is ignored, so the admin page can
say which features earn their keep.

`AssistantQuery`: each Ask question, how it was asked and how it was
answered, so the questions it can't answer show what to build next (Lite
plan, BACKEND.md §3).
"""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AISuggestionEvent(Base):
    __tablename__ = "ai_suggestion_events"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    feature: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    event: Mapped[str] = mapped_column(String(10), nullable=False)  # SHOWN | USED
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # What it was about (an offer, deal, player or enquiry id), to pair a use
    # with the suggestion it used.
    ref: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )


class AssistantQuery(Base):
    __tablename__ = "assistant_queries"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    question: Mapped[str] = mapped_column(String(500), nullable=False)
    input: Mapped[str] = mapped_column(String(10), nullable=False, default="text")  # text | voice
    lite: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    had_proposal: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    links_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # No usable answer: the model was unavailable, failed, or said the facts
    # don't cover it.
    fallback: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
