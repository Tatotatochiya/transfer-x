import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy import DateTime, ForeignKey, JSON, Numeric, String, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class PlayerStats(Base):
    __tablename__ = "player_stats"
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    player_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), index=True)
    vendor: Mapped[str] = mapped_column(String(100), nullable=False)
    league_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    season: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # Core
    goals: Mapped[int] = mapped_column(default=0)
    assists: Mapped[int] = mapped_column(default=0)
    appearances: Mapped[int] = mapped_column(default=0)
    avg_rating: Mapped[Decimal | None] = mapped_column(Numeric(4, 2), nullable=True)
    form_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    minutes: Mapped[int | None] = mapped_column(nullable=True)
    # Team context
    team_vendor_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    team_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # Games detail
    lineups: Mapped[int | None] = mapped_column(nullable=True)
    shirt_number: Mapped[int | None] = mapped_column(nullable=True)
    # Shots
    shots_total: Mapped[int | None] = mapped_column(nullable=True)
    shots_on_target: Mapped[int | None] = mapped_column(nullable=True)
    # Passing
    key_passes: Mapped[int | None] = mapped_column(nullable=True)
    pass_accuracy: Mapped[int | None] = mapped_column(nullable=True)
    # Defending
    tackles_total: Mapped[int | None] = mapped_column(nullable=True)
    interceptions: Mapped[int | None] = mapped_column(nullable=True)
    blocks: Mapped[int | None] = mapped_column(nullable=True)
    # Duels
    duels_total: Mapped[int | None] = mapped_column(nullable=True)
    duels_won: Mapped[int | None] = mapped_column(nullable=True)
    # Dribbles
    dribbles_attempts: Mapped[int | None] = mapped_column(nullable=True)
    dribbles_success: Mapped[int | None] = mapped_column(nullable=True)
    # Discipline
    yellow_cards: Mapped[int | None] = mapped_column(nullable=True)
    red_cards: Mapped[int | None] = mapped_column(nullable=True)
    fouls_committed: Mapped[int | None] = mapped_column(nullable=True)
    fouls_drawn: Mapped[int | None] = mapped_column(nullable=True)
    # Goalkeeper
    saves: Mapped[int | None] = mapped_column(nullable=True)
    goals_conceded: Mapped[int | None] = mapped_column(nullable=True)
    # Penalty
    penalty_scored: Mapped[int | None] = mapped_column(nullable=True)
    penalty_missed: Mapped[int | None] = mapped_column(nullable=True)
    penalty_won: Mapped[int | None] = mapped_column(nullable=True)
    penalty_committed: Mapped[int | None] = mapped_column(nullable=True)
    penalty_saved: Mapped[int | None] = mapped_column(nullable=True)
    # Cards
    cards_yellowred: Mapped[int | None] = mapped_column(nullable=True)
    # Substitutions
    substitutes_in: Mapped[int | None] = mapped_column(nullable=True)
    substitutes_out: Mapped[int | None] = mapped_column(nullable=True)
    substitutes_bench: Mapped[int | None] = mapped_column(nullable=True)
    # Additional
    passes_total: Mapped[int | None] = mapped_column(nullable=True)
    dribbles_past: Mapped[int | None] = mapped_column(nullable=True)  # times dribbled past (defensive)
    position_played: Mapped[str | None] = mapped_column(String(10), nullable=True)  # position for this league/season
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    # No DB-level unique constraint here — handle in service with IS NULL logic


class PlayerStatsSnapshot(Base):
    __tablename__ = "player_stats_snapshots"
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    player_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), index=True)
    vendor: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())


class PlayerForm(Base):
    __tablename__ = "player_forms"
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    player_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), unique=True, index=True)
    form_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    games_considered: Mapped[int] = mapped_column(default=5)
    key_metrics: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    trend: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    last_updated: Mapped[datetime] = mapped_column(DateTime, default=func.now())


class VendorSyncState(Base):
    __tablename__ = "vendor_sync_states"
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    vendor: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    error_count: Mapped[int] = mapped_column(default=0)
