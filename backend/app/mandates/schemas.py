import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from app.mandates.models import MandateStatus


class CreateMandateRequest(BaseModel):
    player_id: uuid.UUID
    start_date: date | None = None
    end_date: date | None = None
    exclusive: bool = False
    territory: str | None = None


class MandateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    agent_id: uuid.UUID
    player_id: uuid.UUID
    start_date: date | None
    end_date: date | None
    exclusive: bool
    territory: str | None
    status: MandateStatus
    created_at: datetime
