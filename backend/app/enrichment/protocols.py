"""Provider-agnostic protocols and DTOs for player enrichment (TRA-66)."""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Protocol

from app.players.models import ValuationSource, WageSource


@dataclass
class ValuationResult:
    market_value: Decimal
    market_value_currency: str
    valuation_low: Decimal | None
    valuation_high: Decimal | None
    source: ValuationSource
    as_of: date


@dataclass
class ContractResult:
    contract_expiry: date | None
    contract_signed: date | None
    wage_weekly: Decimal | None
    wage_currency: str | None
    wage_verified: bool
    source: WageSource


class ValuationProvider(Protocol):
    """Fetch market value for a player by their external provider ID."""
    async def get_valuation(self, external_id: str) -> ValuationResult | None: ...


class ContractProvider(Protocol):
    """Fetch contract + wage data for a player by their external provider slug."""
    async def get_contract(self, external_id: str) -> ContractResult | None: ...
