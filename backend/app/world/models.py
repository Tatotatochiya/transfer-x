import uuid
from datetime import datetime
from sqlalchemy import DateTime, String, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class WorldTeam(Base):
    """Vendor-synced club/team — not a registered marketplace user."""

    __tablename__ = "world_teams"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    vendor: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    vendor_id: Mapped[str] = mapped_column(String(200), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    league_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    crest_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    season: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("vendor", "vendor_id", name="uq_world_teams_vendor_id"),
    )


class WorldLeague(Base):
    __tablename__ = "world_leagues"
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    vendor: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    league_id: Mapped[str] = mapped_column(String(200), nullable=False)  # vendor's own ID
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    season: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    __table_args__ = (
        UniqueConstraint("vendor", "league_id", name="uq_world_leagues_vendor_league"),
    )
