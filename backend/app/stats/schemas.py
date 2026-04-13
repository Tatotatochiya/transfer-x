import uuid
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel


class PlayerStatsUpsertRequest(BaseModel):
    vendor: str
    league_id: str | None = None
    season: str | None = None
    goals: int = 0
    assists: int = 0
    appearances: int = 0
    avg_rating: Decimal | None = None
    form_score: Decimal | None = None


class PlayerStatsResponse(BaseModel):
    id: uuid.UUID
    player_id: uuid.UUID
    vendor: str
    league_id: str | None
    season: str | None
    # Core
    goals: int
    assists: int
    appearances: int
    avg_rating: float | None
    form_score: float | None
    minutes: int | None
    # Team context
    team_vendor_id: str | None
    team_name: str | None
    # Games detail
    lineups: int | None
    shirt_number: int | None
    # Shots
    shots_total: int | None
    shots_on_target: int | None
    # Passing
    key_passes: int | None
    pass_accuracy: int | None
    # Defending
    tackles_total: int | None
    interceptions: int | None
    blocks: int | None
    # Duels
    duels_total: int | None
    duels_won: int | None
    # Dribbles
    dribbles_attempts: int | None
    dribbles_success: int | None
    # Discipline
    yellow_cards: int | None
    red_cards: int | None
    fouls_committed: int | None
    fouls_drawn: int | None
    # Goalkeeper
    saves: int | None
    goals_conceded: int | None
    # Penalty
    penalty_scored: int | None
    penalty_missed: int | None
    updated_at: datetime

    model_config = {"from_attributes": True}


class PlayerFormUpsertRequest(BaseModel):
    form_score: Decimal
    games_considered: int = 5
    key_metrics: dict | None = None


class PlayerFormResponse(BaseModel):
    id: uuid.UUID
    player_id: uuid.UUID
    form_score: float
    games_considered: int
    key_metrics: dict | None
    trend: float | None
    last_updated: datetime

    model_config = {"from_attributes": True}


class SnapshotCreateRequest(BaseModel):
    vendor: str
    payload: dict


class SnapshotResponse(BaseModel):
    id: uuid.UUID
    player_id: uuid.UUID
    vendor: str
    payload: dict
    fetched_at: datetime

    model_config = {"from_attributes": True}


class VendorSyncStateUpsertRequest(BaseModel):
    success: bool
    error: str | None = None


class VendorSyncStateResponse(BaseModel):
    id: uuid.UUID
    vendor: str
    last_sync_at: datetime | None
    last_success_at: datetime | None
    last_error: str | None
    error_count: int

    model_config = {"from_attributes": True}
