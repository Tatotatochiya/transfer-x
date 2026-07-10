import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

from app.valuation.constants import DivergenceBand, ValuationConfidence


class ValuationBreakdownEntry(BaseModel):
    label: str
    value: str
    norm: float
    weight: int
    contribution: float


class ValuationDivergence(BaseModel):
    reference_price: Decimal
    pct: float
    band: DivergenceBand


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
    divergence: ValuationDivergence | None = None

    model_config = {"from_attributes": True}


class ValuationBatchResponse(BaseModel):
    valuations: dict[str, ValuationResponse]
