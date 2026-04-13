import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Numeric, String, Text, Uuid, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class PlayerPosition(str, enum.Enum):
    GK = "GK"
    DEF = "DEF"
    MID = "MID"
    FWD = "FWD"


class PlayerVisibility(str, enum.Enum):
    PUBLIC = "PUBLIC"
    CLUBS_ONLY = "CLUBS_ONLY"
    PRIVATE = "PRIVATE"


class PlayerStatus(str, enum.Enum):
    CONTRACTED = "CONTRACTED"
    FREE_AGENT = "FREE_AGENT"


class Player(Base):
    __tablename__ = "players"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    age: Mapped[int | None] = mapped_column(nullable=True)
    nationality: Mapped[str | None] = mapped_column(String(100), nullable=True)
    position: Mapped[PlayerPosition | None] = mapped_column(
        SAEnum(PlayerPosition, name="playerposition"), nullable=True, index=True
    )
    current_club_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("clubs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    visibility: Mapped[PlayerVisibility] = mapped_column(
        SAEnum(PlayerVisibility, name="playervisibility"),
        nullable=False,
        default=PlayerVisibility.PUBLIC,
        index=True,
    )
    status: Mapped[PlayerStatus] = mapped_column(
        SAEnum(PlayerStatus, name="playerstatus"),
        nullable=False,
        default=PlayerStatus.FREE_AGENT,
        index=True,
    )
    open_to_offers: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    photo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    vendor_id: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True)
    team_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # Bio fields populated from vendor API data
    firstname: Mapped[str | None] = mapped_column(String(100), nullable=True)
    lastname: Mapped[str | None] = mapped_column(String(100), nullable=True)
    height: Mapped[str | None] = mapped_column(String(20), nullable=True)   # e.g. "183 cm"
    weight: Mapped[str | None] = mapped_column(String(20), nullable=True)   # e.g. "76 kg"
    birth_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    birth_place: Mapped[str | None] = mapped_column(String(200), nullable=True)
    birth_country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    world_team_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("world_teams.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    contracts: Mapped[list["Contract"]] = relationship(
        "Contract", back_populates="player", cascade="all, delete-orphan"
    )
    current_club: Mapped["app.clubs.models.Club | None"] = relationship(  # type: ignore[name-defined]
        "Club", foreign_keys=[current_club_id]
    )
    world_team: Mapped["app.world.models.WorldTeam | None"] = relationship(  # type: ignore[name-defined]
        "WorldTeam", foreign_keys=[world_team_id]
    )


class Contract(Base):
    __tablename__ = "contracts"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    player_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("players.id", ondelete="CASCADE"), nullable=False, index=True
    )
    club_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("clubs.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    wage_weekly: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    release_clause: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    club_valuation: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    notes: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    player: Mapped["Player"] = relationship("Player", back_populates="contracts")
    club: Mapped["app.clubs.models.Club"] = relationship("Club", foreign_keys=[club_id])  # type: ignore[name-defined]


class PlayerTransfer(Base):
    """Transfer history cached from API-Football /transfers endpoint."""
    __tablename__ = "player_transfers"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    player_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("players.id", ondelete="CASCADE"), nullable=False, index=True
    )
    vendor: Mapped[str] = mapped_column(String(50), nullable=False)
    transfer_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    transfer_type: Mapped[str | None] = mapped_column(String(50), nullable=True)  # "Transfer", "Loan"
    team_in_vendor_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    team_in_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    team_in_crest_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    team_out_vendor_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    team_out_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    team_out_crest_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    fee_display: Mapped[str | None] = mapped_column(String(100), nullable=True)  # e.g. "€50M", "Free", "Loan"
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class PlayerInjury(Base):
    """Injury/sidelined history cached from API-Football /sidelined endpoint."""
    __tablename__ = "player_injuries"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    player_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("players.id", ondelete="CASCADE"), nullable=False, index=True
    )
    vendor: Mapped[str] = mapped_column(String(50), nullable=False)
    league_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    season: Mapped[str | None] = mapped_column(String(20), nullable=True)
    fixture_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    injury_type: Mapped[str | None] = mapped_column(String(200), nullable=True)  # e.g. "Knee Injury"
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    games_absent: Mapped[int | None] = mapped_column(nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
