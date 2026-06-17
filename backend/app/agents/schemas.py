import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from app.mandates.models import MandateStatus


class AgentProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    display_name: str
    agency_name: str
    licence_no: str | None
    country: str
    verified: bool
    created_at: datetime


class AgentUpdateRequest(BaseModel):
    display_name: str | None = None
    agency_name: str | None = None
    licence_no: str | None = None
    country: str | None = None


class RepresentedPlayerItem(BaseModel):
    mandate_id: uuid.UUID
    player_id: uuid.UUID
    player_name: str
    player_position: str | None
    exclusive: bool
    start_date: date | None
    end_date: date | None
    status: MandateStatus
