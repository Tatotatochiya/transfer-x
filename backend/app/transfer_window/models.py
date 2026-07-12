"""Transfer window model."""
import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class TransferWindow(Base):
    __tablename__ = "transfer_windows"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(sa.String(200), nullable=False)
    association: Mapped[str | None] = mapped_column(sa.String(100), nullable=True, index=True)
    opens_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False, index=True)
    closes_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False, index=True)
    # Re-audit: "deal sheet" grace — a deal confirmed while this window was open
    # may still complete for this many hours after closes_at, even though the
    # window is no longer open for *new* deals. Mirrors real deadline-day practice.
    grace_period_hours: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=24, server_default="24")
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )
