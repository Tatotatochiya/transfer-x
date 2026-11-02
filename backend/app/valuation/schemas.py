import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.valuation.constants import DivergenceBand, ValuationConfidence


class ValuationBreakdownEntry(BaseModel):
    label: str
    value: str
    norm: float
    weight: int
    contribution: float


class ValuationDriver(BaseModel):
    """One step of the market-v2 value build-up (anchor → … → fair value)."""

    key: str
    label: str
    detail: str
    factor: float | None
    value_after: float


class ValuationDivergence(BaseModel):
    reference_price: Decimal
    pct: float
    band: DivergenceBand


class LastTransfer(BaseModel):
    fee_gbp: float
    fee_display: str | None = None  # as reported, e.g. "€ 116.6M"; None for a TransferX deal
    date: str
    from_club: str | None = Field(None, alias="from")
    to_club: str | None = Field(None, alias="to")
    source: str  # "API-Football" | "TransferX"

    model_config = {"populate_by_name": True}


class ValuationResponse(BaseModel):
    player_id: uuid.UUID
    fair_value: Decimal
    fair_value_low: Decimal
    fair_value_high: Decimal
    currency: str
    performance_score: Decimal
    confidence: ValuationConfidence
    model_version: str
    league_tier: int
    age_factor: Decimal
    # Feature-snapshot context the UI breakdown popover shows ("Age 25 — peak
    # years", "2,700 minutes this season"); sourced from the stored inputs_json.
    age: int | None = None
    minutes: int | None = None
    as_of: datetime
    breakdown: list[ValuationBreakdownEntry]
    # market-v2: the value build-up, and how many comparable transfers priced
    # it. Empty / null on boxscore-v1 rows.
    drivers: list[ValuationDriver] = []
    comparables_used: int | None = None
    divergence: ValuationDivergence | None = None
    # What a club last paid for him (players/last_fee.py), shown beside the
    # model's value so it can be checked against a real figure.
    last_transfer: LastTransfer | None = None

    model_config = {"from_attributes": True}


class ValuationBatchResponse(BaseModel):
    valuations: dict[str, ValuationResponse]
