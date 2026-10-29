"""Demo runs and their change journal (app/demo/journal.py)."""
import uuid
from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, ForeignKey, Integer, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class DemoRun(Base):
    """One tester's demo: everything they do while it's active, and what it
    sets off, is journaled so `reset` can put it back."""
    __tablename__ = "demo_runs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    club_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("clubs.id", ondelete="SET NULL"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE", index=True)  # ACTIVE | RESET | KEPT
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_by_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    # What reset did: {"undone": n, "skipped": [{"table", "pk", "why"}]}.
    report: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class DemoChange(Base):
    """One row a demo inserted, changed or deleted, in the order it happened.
    `before`/`after` hold only the changed columns for an update, the whole
    row for a delete, nothing for an insert. Values are tagged JSON
    (journal._enc) so reset can restore their types."""
    __tablename__ = "demo_changes"

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("demo_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    table_name: Mapped[str] = mapped_column(String(64), nullable=False)
    pk: Mapped[str] = mapped_column(Text, nullable=False)  # canonical JSON of the primary key
    op: Mapped[str] = mapped_column(String(10), nullable=False)  # insert | update | delete
    before: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    after: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
