import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, field_validator

from app.common.schemas import WhoseMove
from app.offers.models import OfferEventType, OfferStatus
from app.players.schemas import ActiveDealStub


class ClubSummary(BaseModel):
    id: uuid.UUID
    name: str
    model_config = {"from_attributes": True}


class PlayerSummary(BaseModel):
    id: uuid.UUID
    name: str
    position: str | None = None
    model_config = {"from_attributes": True}


# ── Offer schemas ─────────────────────────────────────────────────────────────


class OfferCreateRequest(BaseModel):
    player_id: uuid.UUID
    sale_id: uuid.UUID | None = None
    to_club_id: uuid.UUID | None = None
    fee_amount: Decimal | None = None
    wage_weekly: Decimal | None = None
    contract_years: int | None = None
    contract_end_date: date | None = None
    add_ons: dict = {}
    expires_at: datetime | None = None
    # Approach without disclosing the buying club; the seller sees only the
    # league until they accept.
    is_anonymous: bool = False

    @field_validator("fee_amount", "wage_weekly", mode="before")
    @classmethod
    def non_negative(cls, v):
        if v is not None and v < 0:
            raise ValueError("must be non-negative")
        return v


class OfferCounterRequest(BaseModel):
    fee_amount: Decimal | None = None
    wage_weekly: Decimal | None = None
    contract_years: int | None = None
    contract_end_date: date | None = None
    add_ons: dict | None = None
    expires_at: datetime | None = None


class OfferImproveRequest(BaseModel):
    """Item 2: the buyer raising their own pending offer, bypassing turn order."""
    fee_amount: Decimal | None = None
    wage_weekly: Decimal | None = None
    add_ons: dict | None = None


class OfferMessageRequest(BaseModel):
    body: str

    @field_validator("body")
    @classmethod
    def not_empty(cls, v):
        if not v.strip():
            raise ValueError("message body cannot be empty")
        return v.strip()


class OfferMessageResponse(BaseModel):
    id: uuid.UUID
    offer_id: uuid.UUID
    sender_club_id: uuid.UUID | None
    body: str
    created_at: datetime
    sender_club: ClubSummary | None = None
    model_config = {"from_attributes": True}


class OfferEventResponse(BaseModel):
    id: uuid.UUID
    offer_id: uuid.UUID
    event_type: OfferEventType
    actor_club_id: uuid.UUID | None
    payload: dict
    created_at: datetime
    model_config = {"from_attributes": True}


class OfferResponse(BaseModel):
    id: uuid.UUID
    player_id: uuid.UUID
    sale_id: uuid.UUID | None
    # Nullable because an anonymous buyer is masked out of their own offer for
    # everyone but themselves and staff. The *id* has to go too, not just the
    # name — anyone holding it could read the club straight off GET /clubs/{id}.
    from_club_id: uuid.UUID | None
    to_club_id: uuid.UUID | None
    last_actor_club_id: uuid.UUID | None
    fee_amount: Decimal | None
    wage_weekly: Decimal | None
    contract_years: int | None
    contract_end_date: date | None
    add_ons: dict
    status: OfferStatus
    expires_at: datetime | None
    last_action_at: datetime
    created_at: datetime
    player: PlayerSummary | None = None
    from_club: ClubSummary | None = None
    to_club: ClubSummary | None = None
    messages: list[OfferMessageResponse] = []
    events: list[OfferEventResponse] = []
    # B1: set explicitly after model_validate() by the router — needs the
    # viewer's own club id, which isn't an attribute of the Offer row itself.
    whose_move: WhoseMove | None = None
    # The deal this offer produced, on the list and detail endpoints. `status`
    # above stays truthful about the *offer* — it really was accepted — but that
    # is not what became of the transfer, and ACCEPTED renders green whether the
    # deal completed or collapsed at personal terms. Readers need both facts.
    deal: ActiveDealStub | None = None
    # Both parties always see *that* an offer is anonymous — a seller has to
    # know they are dealing with an undisclosed club, even before they know
    # which one. Only the identity is withheld, never the fact.
    is_anonymous: bool = False
    # Populated only while the buyer is actually masked from this viewer: the
    # one thing they do get told about the counterparty.
    buyer_league_name: str | None = None
    model_config = {"from_attributes": True}
