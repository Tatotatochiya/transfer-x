"""Transfer window model."""
import uuid
from datetime import date, datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class TransferWindow(Base):
    """A registration period: when a club in `country` can register a player
    it has signed. No country means every club (service.windows_for)."""
    __tablename__ = "transfer_windows"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(sa.String(200), nullable=False)
    country: Mapped[str | None] = mapped_column(sa.String(100), nullable=True, index=True)
    opens_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False, index=True)
    closes_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False, index=True)
    # Where an admin read the dates (FIFA's registration period calendar, the
    # league's announcement) and when. No feed publishes them.
    source_url: Mapped[str | None] = mapped_column(sa.String(500), nullable=True)
    checked_on: Mapped[date | None] = mapped_column(sa.Date, nullable=True)
    # When clubs with deals waiting on this window were told it opened.
    opened_notice_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )
