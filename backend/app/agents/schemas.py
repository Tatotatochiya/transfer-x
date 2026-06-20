import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.agents.models import CommissionStatus, InvitationStatus
from app.mandates.models import ClientStatus, MandateStatus


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
    client_status: ClientStatus


# ── Roster import ─────────────────────────────────────────────────────────────

class MatchCandidate(BaseModel):
    player_id: str
    player_name: str
    player_position: str | None
    player_club: str | None


class RosterPreviewRow(BaseModel):
    row_index: int
    name: str
    dob: str | None
    nationality: str | None
    position: str | None
    current_club: str | None
    contract_expiry: str | None
    match_status: Literal["matched", "ambiguous", "no_match"]
    match_candidates: list[MatchCandidate]


class RosterPreviewResponse(BaseModel):
    rows: list[RosterPreviewRow]


class ImportRow(BaseModel):
    action: Literal["create", "link", "skip"]
    player_id: str | None = None  # UUID string, required for "link"
    # fields for "create"
    name: str | None = None
    dob: date | None = None
    nationality: str | None = None
    position: str | None = None
    current_club: str | None = None


class RosterImportRequest(BaseModel):
    rows: list[ImportRow]
    exclusive: bool = False
    start_date: date | None = None
    end_date: date | None = None
    territory: str | None = None


class RosterImportResult(BaseModel):
    created: int
    linked: int
    skipped: int
    errors: list[str]
    mandate_ids: list[str]


# ── Deal invitations (TRA-125) ─────────────────────────────────────────────────

class DealSummary(BaseModel):
    id: uuid.UUID
    agreed_fee: Decimal
    buyer_club_name: str | None = None
    seller_club_name: str | None = None
    player_name: str | None = None


class InvitationResponse(BaseModel):
    id: uuid.UUID
    deal_id: uuid.UUID
    status: InvitationStatus
    created_at: datetime
    deal: DealSummary | None = None


# ── Pipeline view (TRA-130) ───────────────────────────────────────────────────

class PipelineDealItem(BaseModel):
    deal_id: uuid.UUID
    player_id: uuid.UUID
    player_name: str
    player_photo_url: str | None
    buyer_club_name: str | None
    seller_club_name: str | None
    stage: str
    deal_status: str
    agreed_fee: Decimal | None
    commission_amount: Decimal | None
    commission_pct: Decimal | None
    action_required: bool
    action_description: str | None
    created_at: datetime
    updated_at: datetime


class AgentPipelineResponse(BaseModel):
    deals_in_progress: int
    deals_completed_this_window: int
    total_commission_pipeline: Decimal
    items: list[PipelineDealItem]


class AgentCommissionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    deal_id: uuid.UUID
    agent_id: uuid.UUID
    window_id: uuid.UUID | None
    window_label: str | None
    amount: Decimal
    pct: Decimal | None
    payer: str | None
    status: CommissionStatus
    created_at: datetime
    confirmed_at: datetime | None
    invoiced_at: datetime | None
    paid_at: datetime | None


class CommissionSummary(BaseModel):
    earned: Decimal
    pipeline: Decimal
    outstanding: Decimal
    total: int


class AgentCommissionsResponse(BaseModel):
    summary: CommissionSummary
    commissions: list[AgentCommissionResponse]


class CommissionStatusUpdate(BaseModel):
    status: CommissionStatus
