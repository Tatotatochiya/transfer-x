import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, field_validator

from app.sales.models import BidStatus, SaleStatus, SaleType


# ── Sale schemas ──────────────────────────────────────────────────────────────

class SaleCreateRequest(BaseModel):
    player_id: uuid.UUID
    sale_type: SaleType
    asking_price: Decimal | None = None
    reserve_price: Decimal | None = None
    min_increment: Decimal = Decimal("500000")
    deadline: datetime | None = None
    notes: str | None = None

    @field_validator("asking_price", "reserve_price", "min_increment", mode="before")
    @classmethod
    def non_negative(cls, v):
        if v is not None and v < 0:
            raise ValueError("must be non-negative")
        return v


class SellerClubSummary(BaseModel):
    id: uuid.UUID
    name: str

    model_config = {"from_attributes": True}


class PlayerSummary(BaseModel):
    id: uuid.UUID
    name: str
    position: str | None = None

    model_config = {"from_attributes": True}


class SaleResponse(BaseModel):
    id: uuid.UUID
    player_id: uuid.UUID
    seller_club_id: uuid.UUID
    sale_type: SaleType
    asking_price: Decimal | None
    reserve_price: Decimal | None
    min_increment: Decimal
    deadline: datetime | None
    notes: str | None
    status: SaleStatus
    created_at: datetime
    updated_at: datetime
    player: PlayerSummary | None = None
    seller_club: SellerClubSummary | None = None
    # auction summary fields (populated for AUCTION type)
    bid_count: int = 0
    best_bid: Decimal | None = None
    minimum_next_bid: Decimal | None = None
    reserve_met: bool = False

    model_config = {"from_attributes": True}


# ── Bid schemas ───────────────────────────────────────────────────────────────

class BidCreateRequest(BaseModel):
    amount: Decimal
    wage_offer_weekly: Decimal | None = None
    notes: str | None = None

    @field_validator("amount", mode="before")
    @classmethod
    def positive(cls, v):
        if v <= 0:
            raise ValueError("bid amount must be positive")
        return v


class BidderClubSummary(BaseModel):
    id: uuid.UUID
    name: str

    model_config = {"from_attributes": True}


class BidResponse(BaseModel):
    id: uuid.UUID
    sale_id: uuid.UUID
    buyer_club_id: uuid.UUID
    amount: Decimal
    wage_offer_weekly: Decimal | None
    notes: str | None
    status: BidStatus
    created_at: datetime
    updated_at: datetime
    buyer_club: BidderClubSummary | None = None

    model_config = {"from_attributes": True}


# ── Deal stub schema ──────────────────────────────────────────────────────────

class DealStubResponse(BaseModel):
    id: uuid.UUID
    sale_id: uuid.UUID | None
    bid_id: uuid.UUID | None
    buyer_club_id: uuid.UUID
    seller_club_id: uuid.UUID
    player_id: uuid.UUID
    agreed_fee: Decimal
    agreed_wage_weekly: Decimal | None
    status: str
    stage: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Order book schemas ────────────────────────────────────────────────────────

class OrderBookClubSummary(BaseModel):
    id: uuid.UUID
    name: str
    crest_url: str | None = None
    model_config = {"from_attributes": True}


class OrderBookEntry(BaseModel):
    """One row in the order book."""
    rank: int
    kind: str  # "bid" | "offer"
    id: uuid.UUID
    club: OrderBookClubSummary | None = None
    fee_amount: Decimal | None
    wage_weekly: Decimal | None = None
    status: str
    is_countered: bool
    is_active: bool
    last_action_at: datetime


class OrderBookTier(BaseModel):
    label: str
    count: int
    includes_yours: bool


class OrderBookResponse(BaseModel):
    sale_id: uuid.UUID | None = None
    role: str  # "seller" | "buyer"
    active_count: int
    # Seller fields
    entries: list[OrderBookEntry] = []
    summary: str = ""
    # Buyer fields
    tiers: list[OrderBookTier] = []
    your_rank: int | None = None
    is_leading: bool = False
    your_entry: OrderBookEntry | None = None
