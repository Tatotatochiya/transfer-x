import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, model_validator

from app.agents.models import AgreementStatus, CommissionPayer, NegotiationStatus  # noqa: F401 (re-exported)
from app.deals.models import ClauseStatus, ClauseType, DealStage, DealStatus, DealType, MedicalStatus


class ClubSummary(BaseModel):
    id: uuid.UUID
    name: str
    crest_url: str | None = None
    model_config = {"from_attributes": True}


class PlayerSummary(BaseModel):
    id: uuid.UUID
    name: str
    position: str | None = None
    model_config = {"from_attributes": True}


class DealNoteResponse(BaseModel):
    id: uuid.UUID
    deal_id: uuid.UUID
    author_club_id: uuid.UUID | None
    body: str
    created_at: datetime
    author_club: ClubSummary | None = None
    model_config = {"from_attributes": True}


class DealNoteRequest(BaseModel):
    body: str


class TransferActivityItem(BaseModel):
    id: uuid.UUID
    player: PlayerSummary | None = None
    buyer_club: ClubSummary | None = None
    seller_club: ClubSummary | None = None
    agreed_fee: Decimal
    is_auction_deal: bool = False
    completed_at: datetime | None
    created_at: datetime
    model_config = {"from_attributes": True}


# ── Analytics schemas ─────────────────────────────────────────────────────────

class ClubTransferStat(BaseModel):
    club: ClubSummary
    count: int
    total_spend: Decimal

    model_config = {"from_attributes": True}


class PositionBreakdown(BaseModel):
    position: str
    count: int
    total_spend: Decimal


class OngoingStats(BaseModel):
    total_count: int
    by_stage: dict[str, int]
    total_committed_fees: Decimal


class CompletedStats(BaseModel):
    total_count: int
    total_spend: Decimal
    avg_fee: Decimal | None
    highest_fee_deal: TransferActivityItem | None
    top_transfers: list[TransferActivityItem]
    most_active_buyer: ClubTransferStat | None
    most_active_seller: ClubTransferStat | None
    by_position: list[PositionBreakdown]
    auction_count: int
    offer_count: int
    recent_30d_count: int
    recent_30d_spend: Decimal


class TransferAnalytics(BaseModel):
    completed: CompletedStats
    ongoing: OngoingStats


# ── Clause schemas (TRA-57) ───────────────────────────────────────────────────

class DealClauseResponse(BaseModel):
    id: uuid.UUID
    deal_id: uuid.UUID
    clause_type: ClauseType
    trigger_description: str
    amount: Decimal
    cap: Decimal | None
    status: ClauseStatus
    created_at: datetime
    model_config = {"from_attributes": True}


class CreateClauseRequest(BaseModel):
    clause_type: ClauseType
    trigger_description: str
    amount: Decimal
    cap: Decimal | None = None


class UpdateClauseStatusRequest(BaseModel):
    status: ClauseStatus


# ── Instalment schemas (TRA-58) ───────────────────────────────────────────────

class InstalmentItem(BaseModel):
    due_date: date
    amount: Decimal


class CreateInstalmentsRequest(BaseModel):
    instalments: list[InstalmentItem]


class DealInstalmentResponse(BaseModel):
    id: uuid.UUID
    deal_id: uuid.UUID
    due_date: date
    amount: Decimal
    paid: bool
    paid_at: datetime | None
    model_config = {"from_attributes": True}


# ── Medical check schemas (TRA-61) ───────────────────────────────────────────

class MedicalCheckResponse(BaseModel):
    id: uuid.UUID
    deal_id: uuid.UUID
    status: MedicalStatus
    notes: str | None = None
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class UpsertMedicalCheckRequest(BaseModel):
    status: MedicalStatus
    notes: str | None = None


# ── Personal terms schemas (TRA-60) ──────────────────────────────────────────

class PersonalTermsResponse(BaseModel):
    id: uuid.UUID
    deal_id: uuid.UUID
    agent_id: uuid.UUID | None = None
    wage_weekly: Decimal | None = None
    signing_bonus: Decimal | None = None
    length_years: int | None = None
    player_consent: AgreementStatus
    player_has_account: bool
    agreed_at: datetime | None = None
    created_at: datetime
    model_config = {"from_attributes": True}


class SetPersonalTermsRequest(BaseModel):
    wage_weekly: Decimal | None = None
    signing_bonus: Decimal | None = None
    length_years: int | None = None


# ── Agent negotiation schemas (TRA-127) ──────────────────────────────────────

class AgentNegotiationResponse(BaseModel):
    id: uuid.UUID
    deal_id: uuid.UUID
    agent_id: uuid.UUID
    status: NegotiationStatus
    # Commission terms — the only thing negotiated at this stage (visible to
    # agent, staff, and buyer club). Personal terms live in PersonalTerms.
    commission_pct: Decimal | None = None
    commission_amount: Decimal | None = None
    commission_payer: CommissionPayer | None = None
    additional_conditions: str | None = None
    club_agreement: AgreementStatus
    created_at: datetime
    agreed_at: datetime | None = None
    model_config = {"from_attributes": True}


class UpdateNegotiationTermsRequest(BaseModel):
    commission_pct: Decimal | None = None
    commission_amount: Decimal | None = None
    commission_payer: CommissionPayer | None = None
    additional_conditions: str | None = None


class NegotiationRespondRequest(BaseModel):
    agreement: AgreementStatus


# ── Update deal request (TRA-56) ──────────────────────────────────────────────

class UpdateDealRequest(BaseModel):
    deal_type: DealType | None = None
    loan_start: date | None = None
    loan_end: date | None = None
    loan_fee: Decimal | None = None
    option_to_buy: Decimal | None = None
    obligation_to_buy: bool | None = None
    obligation_conditions: str | None = None
    sell_on_pct: Decimal | None = None

    @model_validator(mode="after")
    def _validate_sell_on(self) -> "UpdateDealRequest":
        if self.sell_on_pct is not None and not (Decimal("0") <= self.sell_on_pct <= Decimal("1")):
            raise ValueError("sell_on_pct must be between 0 and 1")
        return self


# ── Deal response ─────────────────────────────────────────────────────────────

class DealResponse(BaseModel):
    id: uuid.UUID
    sale_id: uuid.UUID | None
    bid_id: uuid.UUID | None
    offer_id: uuid.UUID | None
    buyer_club_id: uuid.UUID
    seller_club_id: uuid.UUID | None
    player_id: uuid.UUID
    agreed_fee: Decimal
    agreed_wage_weekly: Decimal | None
    status: DealStatus
    stage: DealStage
    # TRA-56
    deal_type: DealType = DealType.PERMANENT
    loan_start: date | None = None
    loan_end: date | None = None
    loan_fee: Decimal | None = None
    option_to_buy: Decimal | None = None
    obligation_to_buy: bool = False
    obligation_conditions: str | None = None
    # TRA-57
    sell_on_pct: Decimal | None = None
    clauses: list[DealClauseResponse] = []
    # TRA-58
    instalments: list[DealInstalmentResponse] = []
    # TRA-59
    agent_commission_pct: Decimal | None = None
    agent_commission_amount: Decimal | None = None
    commission_payer: CommissionPayer | None = None
    commission_agent_id: uuid.UUID | None = None
    # TRA-60
    personal_terms: PersonalTermsResponse | None = None
    # TRA-61
    medical_check: MedicalCheckResponse | None = None
    notes: str | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime
    is_auction_deal: bool = False
    buyer_club: ClubSummary | None = None
    seller_club: ClubSummary | None = None
    player: PlayerSummary | None = None
    deal_notes: list[DealNoteResponse] = []
    model_config = {"from_attributes": True}
