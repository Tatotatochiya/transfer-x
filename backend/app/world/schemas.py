import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class WorldTeamResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    vendor: str
    vendor_id: str
    name: str
    country: str | None
    league_name: str | None
    crest_url: str | None
    season: str | None
    created_at: datetime


class LeagueCreateRequest(BaseModel):
    vendor: str
    league_id: str
    name: str
    country: str | None = None
    season: str | None = None


class LeagueResponse(BaseModel):
    id: uuid.UUID
    vendor: str
    league_id: str
    name: str
    country: str | None
    season: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
