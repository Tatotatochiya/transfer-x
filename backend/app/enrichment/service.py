"""Enrichment write helpers — respect manual overrides (TRA-66)."""
from sqlalchemy.ext.asyncio import AsyncSession

from app.enrichment.protocols import ContractResult, ValuationResult
from app.players.models import Player, ValuationSource, WageSource


async def apply_valuation(db: AsyncSession, player: Player, result: ValuationResult) -> None:
    """Write a provider valuation result onto the player row.

    Manual overrides are never silently clobbered: if valuation_source == MANUAL,
    return without touching the row.
    """
    if player.valuation_source == ValuationSource.MANUAL:
        return
    player.market_value = result.market_value
    player.market_value_currency = result.market_value_currency
    player.valuation_low = result.valuation_low
    player.valuation_high = result.valuation_high
    player.valuation_source = result.source
    player.valuation_as_of = result.as_of
    await db.flush()


async def apply_contract(db: AsyncSession, player: Player, result: ContractResult) -> None:
    """Write a provider contract/wage result onto the player row.

    Manual overrides are never silently clobbered: if wage_source == MANUAL,
    return without touching the row.
    """
    if player.wage_source == WageSource.MANUAL:
        return
    player.contract_expiry = result.contract_expiry
    player.contract_signed = result.contract_signed
    player.wage_weekly = result.wage_weekly
    player.wage_currency = result.wage_currency
    player.wage_source = result.source
    player.wage_verified = result.wage_verified
    await db.flush()
