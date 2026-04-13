"""Fixture model — caches API-Football fixture data per match."""
import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Fixture(Base):
    __tablename__ = "fixtures"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    vendor: Mapped[str] = mapped_column(sa.String(50), nullable=False)
    fixture_vendor_id: Mapped[int] = mapped_column(sa.Integer, nullable=False, index=True)
    league_id: Mapped[int | None] = mapped_column(sa.Integer, nullable=True, index=True)
    season: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    league_name: Mapped[str | None] = mapped_column(sa.String(200), nullable=True)
    round: Mapped[str | None] = mapped_column(sa.String(100), nullable=True)
    home_team_vendor_id: Mapped[int] = mapped_column(sa.Integer, nullable=False, index=True)
    home_team_name: Mapped[str] = mapped_column(sa.String(200), nullable=False)
    home_team_crest_url: Mapped[str | None] = mapped_column(sa.String(512), nullable=True)
    away_team_vendor_id: Mapped[int] = mapped_column(sa.Integer, nullable=False, index=True)
    away_team_name: Mapped[str] = mapped_column(sa.String(200), nullable=False)
    away_team_crest_url: Mapped[str | None] = mapped_column(sa.String(512), nullable=True)
    kickoff_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True, index=True)
    status_short: Mapped[str] = mapped_column(sa.String(10), nullable=False, default="NS")
    status_long: Mapped[str | None] = mapped_column(sa.String(100), nullable=True)
    home_goals: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    away_goals: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    venue_name: Mapped[str | None] = mapped_column(sa.String(200), nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )

    __table_args__ = (
        sa.UniqueConstraint("vendor", "fixture_vendor_id", name="uq_fixtures_vendor_fixture_id"),
    )
