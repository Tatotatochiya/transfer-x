import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.mandates.models import AlertSeverity, AlertType, ClientStatus, MandateStatus


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
    # TRA-134: alert preferences
    alert_contract_expiry_enabled: bool
    alert_contract_expiry_months: int
    alert_valuation_change_enabled: bool
    alert_valuation_change_pct: Decimal
    alert_club_interest_enabled: bool


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
    # TRA-134: alert preferences
    alert_contract_expiry_enabled: bool | None = None
    alert_contract_expiry_months: int | None = None
    alert_valuation_change_enabled: bool | None = None
    alert_valuation_change_pct: Decimal | None = None
    alert_club_interest_enabled: bool | None = None


class ClientAlertResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    mandate_id: uuid.UUID
    agent_id: uuid.UUID
    player_id: uuid.UUID
    alert_type: AlertType
    severity: AlertSeverity
    message: str
    context: dict
    is_read: bool
    created_at: datetime
    player_name: str | None = None
