import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.mandates.models import ClientStatus, MandateStatus


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


class MandateDetailResponse(BaseModel):
    id: uuid.UUID
    agent_id: uuid.UUID
    player_id: uuid.UUID
    start_date: date | None
    end_date: date | None
    exclusive: bool
    territory: str | None
    status: MandateStatus
    created_at: datetime
    # private client fields
    client_status: ClientStatus
    agent_notes: str | None
    preferred_destinations: str | None
    asking_price: Decimal | None
    asking_wage: Decimal | None
    # denormalized player info
    player_name: str
    player_position: str | None
    player_nationality: str | None
    player_age: int | None
    player_club_name: str | None
    contract_expiry: date | None


class UpdateMandateRequest(BaseModel):
    client_status: ClientStatus | None = None
    agent_notes: str | None = None
    preferred_destinations: str | None = None
    asking_price: Decimal | None = None
    asking_wage: Decimal | None = None
    start_date: date | None = None
    end_date: date | None = None
    territory: str | None = None
    exclusive: bool | None = None
