import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, field_validator

from app.players.schemas import ActiveDealStub
from app.sales.models import ListingAvailability, SaleStatus, SaleType
from app.valuation.schemas import ValuationResponse


# ── Sale schemas ──────────────────────────────────────────────────────────────

class SaleCreateRequest(BaseModel):
    player_id: uuid.UUID
    sale_type: SaleType
    # What the club will consider — transfer, loan, or either. Rules in
    # sales/service.validate_listing_terms.
    availability: ListingAvailability = ListingAvailability.TRANSFER
    asking_price: Decimal | None = None
    # The seller's private floor: only the seller and staff see it.
    reserve_price: Decimal | None = None
    # "We'll hear offers until…": the listing closes then (sales.service.close_expired_sales).
    deadline: datetime | None = None
    notes: str | None = None
    # The guide price came from the listing assistant; audited, not binding.
    ai_assisted: bool = False

    @field_validator("asking_price", "reserve_price", mode="before")
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
    photo_url: str | None = None  # his photo, wherever his name is shown

    model_config = {"from_attributes": True}


class SaleResponse(BaseModel):
    id: uuid.UUID
    player_id: uuid.UUID
    seller_club_id: uuid.UUID
    sale_type: SaleType
    availability: ListingAvailability = ListingAvailability.TRANSFER
    asking_price: Decimal | None
    reserve_price: Decimal | None
    deadline: datetime | None
    notes: str | None
    status: SaleStatus
    created_at: datetime
    updated_at: datetime
    player: PlayerSummary | None = None
    seller_club: SellerClubSummary | None = None
    # TRA-91 fair-value signal — populated on the detail endpoint only; null for
    # player-account/anonymous viewers and ineligible players (D6). Divergence
    # on any listing that publishes an asking price (D7 — never against
    # reserve_price).
    fair_value_signal: ValuationResponse | None = None
    # Withdrawn by TransferX staff rather than the seller. The reason is for
    # the seller and staff only.
    cancelled_by_staff: bool = False
    staff_cancel_reason: str | None = None
    # Populated on the detail endpoint only, like fair_value_signal. Answers the
    # question a resolved listing otherwise leaves open — *why* is this closed?
    # Player-scoped (not sale-scoped) on purpose: it stays correct for listings
    # closed before deals began carrying sale_id.
    active_deal: ActiveDealStub | None = None

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
    kind: str  # "offer"
    id: uuid.UUID
    club: OrderBookClubSummary | None = None
    fee_amount: Decimal | None
    wage_weekly: Decimal | None = None
    # Offers only: a loan's money is its loan fee, and the two must not be
    # read as the same figure.
    deal_type: str | None = None
    loan_fee: Decimal | None = None
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
