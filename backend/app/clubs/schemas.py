import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.clubs.models import ClubRole




class ClubFinanceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    transfer_budget_total: Decimal
    wage_budget_total_weekly: Decimal
    transfer_reserved: Decimal
    wage_reserved_weekly: Decimal
    transfer_committed: Decimal
    wage_committed_weekly: Decimal
    transfer_remaining: Decimal
    wage_remaining_weekly: Decimal
    updated_at: datetime


class ClubResponse(BaseModel):
    """Full club view — returned to the owning user or staff."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    country: str | None
    city: str | None
    league_name: str | None
    crest_url: str | None
    role: ClubRole
    created_at: datetime
    finance: ClubFinanceResponse | None = None
    my_role: str | None = None  # OWNER | MANAGER | READONLY — set by router, not DB


class ClubPublicResponse(BaseModel):
    """Minimal club view — returned in public lists and on player cards."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    country: str | None
    city: str | None
    league_name: str | None
    crest_url: str | None
    role: ClubRole
    created_at: datetime


class ClubUpdateRequest(BaseModel):
    name: str | None = None
    country: str | None = None
    city: str | None = None
    league_name: str | None = None
    crest_url: str | None = None


# ── Player search views ───────────────────────────────────────────────────────

class PlayerSearchViewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    club_id: uuid.UUID
    name: str
    filters: dict
    is_default: bool
    created_at: datetime
    updated_at: datetime


class PlayerSearchViewCreateRequest(BaseModel):
    name: str
    filters: dict = {}
    is_default: bool = False


class PlayerSearchViewUpdateRequest(BaseModel):
    name: str | None = None
    filters: dict | None = None
    is_default: bool | None = None
