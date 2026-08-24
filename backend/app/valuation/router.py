"""TRA-91: fair-value valuation endpoints.

D6: player accounts get 403 on every endpoint here — the signal is club/agent
decision-support and must never reach the player mid-negotiation.
"""
import logging
import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User, UserType
from app.database import get_db
from app.deps import get_current_superuser, get_current_user
from app.players import service as players_service
from app.players.models import Player, PlayerVisibility
from app.valuation import service
from app.valuation.constants import BATCH_MAX_IDS
from app.valuation.schemas import ValuationBatchResponse, ValuationResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["valuation"])


async def get_non_player_user(current_user: User = Depends(get_current_user)) -> User:
    if current_user.user_type == UserType.PLAYER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Valuations are not available to player accounts",
        )
    return current_user


def _is_visible(player: Player, current_user: User) -> bool:
    """Mirror player_market_detail: PRIVATE → creator only."""
    if player.visibility == PlayerVisibility.PRIVATE:
        return player.created_by_user_id == current_user.id
    return True


@router.get("/players", response_model=ValuationBatchResponse)
async def batch_valuations(
    ids: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_non_player_user),
) -> ValuationBatchResponse:
    """Latest valuation per player id (comma-separated, ≤ 50). Ineligible or
    invisible players are silently omitted — a market grid must not error
    because one card lacks data."""
    raw_ids = [part.strip() for part in ids.split(",") if part.strip()]
    if len(raw_ids) > BATCH_MAX_IDS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"At most {BATCH_MAX_IDS} ids per request",
        )
    try:
        player_ids = [uuid.UUID(part) for part in raw_ids]
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid player id"
        )
    if not player_ids:
        return ValuationBatchResponse(valuations={})

    result = await db.execute(select(Player).where(Player.id.in_(player_ids)))
    visible = [p for p in result.scalars().all() if _is_visible(p, current_user)]

    rows = await service.get_latest_valuations(db, [p.id for p in visible])
    # Without a reference price `build_valuation_response` returns no divergence
    # at all, which is what every batch consumer was silently getting: the market
    # list's "best value first" sort and its under-fair-value counter both read
    # `divergence` and both were dead. One extra query for the whole page, never
    # one per row.
    references = await service.get_reference_prices(db, visible)
    return ValuationBatchResponse(
        valuations={
            str(player_id): service.build_valuation_response(
                row, reference_price=references.get(player_id)
            )
            for player_id, row in rows.items()
        }
    )


@router.get("/players/{player_id}", response_model=ValuationResponse)
async def get_player_valuation(
    player_id: uuid.UUID,
    reference_price: Decimal | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_non_player_user),
) -> ValuationResponse:
    player = await players_service.get_player_by_id(db, player_id)
    if player is None or not _is_visible(player, current_user):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Player not found")

    row = await service.get_latest_valuation(db, player_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No model valuation for this player"
        )
    return service.build_valuation_response(row, reference_price=reference_price)


@router.post("/players/{player_id}/recompute", response_model=ValuationResponse)
async def recompute_player_valuation(
    player_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
) -> ValuationResponse:
    """Staff-only synchronous recompute; appends a new row (history untouched).
    No deal-audit event: inputs_json + computed_at + model_version already give
    the required trail, and the audit log is deal-scoped by design."""
    player = await players_service.get_player_by_id(db, player_id)
    if player is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Player not found")

    row = await service.compute_and_store_valuation(db, player)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Player is not eligible for a model valuation",
        )
    await db.commit()
    logger.info(
        "Valuation recomputed for player %s by %s: fair_value=%s confidence=%s",
        player_id,
        current_user.email,
        row.fair_value,
        row.confidence.value,
    )
    return service.build_valuation_response(row)
