import uuid
from datetime import datetime

from pydantic import BaseModel, field_validator

from app.scouting.models import InterestLevel, InterestStage


class PlayerSummary(BaseModel):
    id: uuid.UUID
    name: str
    position: str | None = None
    status: str | None = None
    open_to_offers: bool = False
    team_name: str | None = None
    model_config = {"from_attributes": True}


# ── Shortlist schemas ─────────────────────────────────────────────────────────


class ShortlistCreateRequest(BaseModel):
    name: str
    description: str | None = None

    @field_validator("name")
    @classmethod
    def not_empty(cls, v):
        if not v.strip():
            raise ValueError("name cannot be empty")
        return v.strip()


class ShortlistUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None


class ShortlistItemRequest(BaseModel):
    player_id: uuid.UUID
    priority: int = 3
    notes: str | None = None

    @field_validator("priority")
    @classmethod
    def valid_priority(cls, v):
        if not (1 <= v <= 5):
            raise ValueError("priority must be between 1 and 5")
        return v


class ShortlistItemUpdateRequest(BaseModel):
    priority: int | None = None
    notes: str | None = None

    @field_validator("priority")
    @classmethod
    def valid_priority(cls, v):
        if v is not None and not (1 <= v <= 5):
            raise ValueError("priority must be between 1 and 5")
        return v


class ShortlistItemResponse(BaseModel):
    id: uuid.UUID
    shortlist_id: uuid.UUID
    player_id: uuid.UUID
    priority: int
    notes: str | None
    created_at: datetime
    player: PlayerSummary | None = None
    model_config = {"from_attributes": True}


class ShortlistResponse(BaseModel):
    id: uuid.UUID
    club_id: uuid.UUID
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime
    items: list[ShortlistItemResponse] = []
    model_config = {"from_attributes": True}


class ShortlistSummaryResponse(BaseModel):
    id: uuid.UUID
    club_id: uuid.UUID
    name: str
    description: str | None
    item_count: int = 0
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


# ── PlayerInterest schemas ────────────────────────────────────────────────────


class InterestUpsertRequest(BaseModel):
    level: InterestLevel
    stage: InterestStage
    notes: str | None = None


class PlayerInterestResponse(BaseModel):
    id: uuid.UUID
    club_id: uuid.UUID
    player_id: uuid.UUID
    level: InterestLevel
    stage: InterestStage
    notes: str | None
    last_touched_at: datetime
    created_at: datetime
    player: PlayerSummary | None = None
    model_config = {"from_attributes": True}


# ── Targets dashboard schema ──────────────────────────────────────────────────


class TargetPlayerResponse(BaseModel):
    player_id: uuid.UUID
    name: str
    position: str | None
    status: str
    open_to_offers: bool
    on_shortlists: list[str]  # shortlist names
    interest_level: str | None
    interest_stage: str | None
