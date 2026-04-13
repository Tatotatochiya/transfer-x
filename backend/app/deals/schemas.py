import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

from app.deals.models import DealStage, DealStatus


class ClubSummary(BaseModel):
    id: uuid.UUID
    name: str
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
