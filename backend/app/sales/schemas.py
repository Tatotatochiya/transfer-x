import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, field_validator

from app.common.schemas import WhoseMove
from app.players.schemas import ActiveDealStub
from app.sales.models import BidStatus, SaleStatus, SaleType
from app.valuation.schemas import ValuationResponse


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
    # auction summary fields (populated for AUCTION type; null for non-seller/staff viewers — TRA-139)
    bid_count: int | None = 0
    best_bid: Decimal | None = None
    minimum_next_bid: Decimal | None = None
    reserve_met: bool = False
    # TRA-91 fair-value signal — populated on the detail endpoint only; null for
    # player-account/anonymous viewers and ineligible players (D6). Divergence
    # on any listing that publishes an asking price, never on an AUCTION
    # (D7 — never against reserve_price or any bid figure).
    fair_value_signal: ValuationResponse | None = None
    # B1
    whose_move: WhoseMove = WhoseMove.NEITHER
    # Populated on the detail endpoint only, like fair_value_signal. Answers the
    # question a resolved listing otherwise leaves open — *why* is this closed?
    # Player-scoped (not sale-scoped) on purpose: it stays correct for listings
    # closed before deals began carrying sale_id.
    active_deal: ActiveDealStub | None = None

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
    # Item 13: free-agent signings have no seller club at all.
    seller_club_id: uuid.UUID | None
    player_id: uuid.UUID
    agreed_fee: Decimal
    agreed_wage_weekly: Decimal | None
    status: str
    stage: str
    deal_type: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Order book schemas ────────────────────────────────────────────────────────

class OrderBookClubSummary(BaseModel):
    # Null when the club is deliberately undisclosed (an anonymous buyer) —
    # there is genuinely no id to hand over, and inventing a placeholder would
    # hand back something that looks resolvable but isn't.
    id: uuid.UUID | None = None
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
