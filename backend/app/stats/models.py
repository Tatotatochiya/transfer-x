import uuid
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import Date, DateTime, ForeignKey, Integer, JSON, Numeric, String, UniqueConstraint, Uuid, func
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
    # Player profile ledger (migration 0087): competition and club labels for
    # each row, and whether the season was a loan spell.
    league_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    league_logo: Mapped[str | None] = mapped_column(String(512), nullable=True)
    team_logo: Mapped[str | None] = mapped_column(String(512), nullable=True)
    is_loan: Mapped[bool | None] = mapped_column(nullable=True)
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


class VendorSyncRun(Base):
    """One row per sync operation invocation — the history VendorSyncState (current-state-only) can't show."""
    __tablename__ = "vendor_sync_runs"
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    vendor: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    operation: Mapped[str] = mapped_column(String(50), nullable=False)  # sync_league | sync_team | sync_player | compute_form
    params: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    success: Mapped[bool] = mapped_column(nullable=False)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    triggered_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    finished_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    duration_ms: Mapped[int] = mapped_column(nullable=False)


# ── Player profile ledger history (migration 0087) ───────────────────────────


class PlayerInjuryFixture(Base):
    """One match a player missed through injury or suspension, from
    API-Football's /injuries. Grouping them gives games missed per injury and
    a season's availability."""
    __tablename__ = "player_injury_fixtures"
    __table_args__ = (UniqueConstraint("player_id", "fixture_vendor_id", name="uq_injury_fixture_player"),)
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    player_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("players.id", ondelete="CASCADE"), nullable=False, index=True
    )
    fixture_vendor_id: Mapped[str] = mapped_column(String(50), nullable=False)
    fixture_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    league_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    league_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    season: Mapped[str | None] = mapped_column(String(20), nullable=True)
    team_vendor_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    injury_type: Mapped[str | None] = mapped_column(String(100), nullable=True)  # "Missing Fixture" / "Questionable"
    reason: Mapped[str | None] = mapped_column(String(200), nullable=True)  # e.g. "Hamstring Injury"
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class PlayerFixtureRating(Base):
    """A player's rating in one recent match, for the form strip's last-5 chips."""
    __tablename__ = "player_fixture_ratings"
    __table_args__ = (UniqueConstraint("player_id", "fixture_vendor_id", name="uq_fixture_rating_player"),)
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    player_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("players.id", ondelete="CASCADE"), nullable=False, index=True
    )
    fixture_vendor_id: Mapped[str] = mapped_column(String(50), nullable=False)
    fixture_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    league_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    team_vendor_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    opponent_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    opponent_logo: Mapped[str | None] = mapped_column(String(512), nullable=True)
    home: Mapped[bool | None] = mapped_column(nullable=True)
    minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rating: Mapped[Decimal | None] = mapped_column(Numeric(4, 2), nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class TeamSeasonFixtures(Base):
    """How many matches a club played in one competition-season, for the
    availability figure (games missed against games played)."""
    __tablename__ = "team_season_fixtures"
    __table_args__ = (UniqueConstraint("team_vendor_id", "league_id", "season", name="uq_team_season_fixtures"),)
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    team_vendor_id: Mapped[str] = mapped_column(String(50), nullable=False)
    league_id: Mapped[str] = mapped_column(String(50), nullable=False)
    season: Mapped[str] = mapped_column(String(20), nullable=False)
    played: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class VendorFetchLog(Base):
    """What a history backfill has already fetched, by key (e.g.
    "player-season:<id>:2023"), so it can stop and resume and a re-run makes
    no repeat calls, including for answers that were empty."""
    __tablename__ = "vendor_fetch_log"
    key: Mapped[str] = mapped_column(String(200), primary_key=True)
    results: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
