"""Enrichment sync job (TRA-67).

Runs via APScheduler (daily). Queries all players with external provider IDs
and calls the active provider adapters to update their enrichment data.
Only runs if the active source is not MANUAL.
"""
import logging

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enrichment.registry import get_active_valuation_source, get_active_wage_source
from app.enrichment.service import apply_contract, apply_valuation
from app.players.models import Player

logger = logging.getLogger(__name__)


async def sync_all_players(db: AsyncSession) -> None:
    """Sync enrichment data for all players with external IDs."""
    val_source = get_active_valuation_source()
    wage_source = get_active_wage_source()

    val_provider = None
    contract_provider = None

    if val_source == "ETV":
        from app.enrichment.etv import ETVAdapter
        val_provider = ETVAdapter()

    if wage_source == "CAPOLOGY":
        from app.enrichment.capology import CapologyAdapter
        contract_provider = CapologyAdapter()

    if val_provider is None and contract_provider is None:
        logger.debug("All enrichment sources are MANUAL — skipping sync")
        return

    # Query players that have at least one relevant external ID
    conditions = []
    if val_provider is not None:
        conditions.append(Player.etv_player_id.is_not(None))
    if contract_provider is not None:
        conditions.append(Player.capology_slug.is_not(None))

    result = await db.execute(select(Player).where(or_(*conditions)))
    players = result.scalars().all()

    val_updated = 0
    contract_updated = 0

    for player in players:
        if val_provider is not None and player.etv_player_id:
            try:
                val_result = await val_provider.get_valuation(player.etv_player_id)
                if val_result is not None:
                    await apply_valuation(db, player, val_result)
                    val_updated += 1
            except Exception:
                logger.exception("Valuation sync failed for player %s", player.id)

        if contract_provider is not None and player.capology_slug:
            try:
                contract_result = await contract_provider.get_contract(player.capology_slug)
                if contract_result is not None:
                    await apply_contract(db, player, contract_result)
                    contract_updated += 1
            except Exception:
                logger.exception("Contract sync failed for player %s", player.id)

    logger.info(
        "Enrichment sync complete: %d valuation updates, %d contract updates (of %d players)",
        val_updated, contract_updated, len(players),
    )
