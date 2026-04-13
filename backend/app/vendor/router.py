"""Vendor sync endpoints."""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.deps import get_current_superuser, get_current_user
from app.auth.models import User
from app.vendor.client import ApiFootballClient, VENDOR
from app.vendor import sync as sync_service

router = APIRouter(prefix="/vendor", tags=["vendor"])


def _get_client() -> ApiFootballClient:
    if not settings.apisports_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="APISPORTS_KEY not configured",
        )
    return ApiFootballClient(settings.apisports_key, settings.api_football_base_url)


class SyncLeagueRequest(BaseModel):
    league_id: int
    season: int
    sleep_ms: int = 0


class SyncPlayerRequest(BaseModel):
    season: int
    league_id: int


class SyncTeamRequest(BaseModel):
    team_id: int
    season: int
    sleep_ms: int = 0


class ComputeFormRequest(BaseModel):
    season: str | None = None
    window_games: int = 5


@router.get("/status")
async def vendor_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all vendor sync states."""
    from app.stats import service as stats_service
    states = await stats_service.list_vendor_sync_states(db)
    from app.stats.schemas import VendorSyncStateResponse
    return [VendorSyncStateResponse.model_validate(s) for s in states]


@router.post("/sync/league")
async def sync_league(
    body: SyncLeagueRequest,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    """Sync all players for a league. Superuser only."""
    client = _get_client()
    try:
        result = await sync_service.sync_league(
            db, body.league_id, body.season, client, body.sleep_ms,
            created_by_user_id=current_user.id,
        )
        await db.commit()
        # Record success
        from app.stats import service as stats_service
        async with db.begin_nested():
            await stats_service.upsert_vendor_sync_state(db, VENDOR, success=True)
        await db.commit()
        return result
    except Exception as exc:
        await db.rollback()
        from app.stats import service as stats_service
        async with db.begin():
            await stats_service.upsert_vendor_sync_state(db, VENDOR, success=False, error=str(exc))
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))


@router.post("/sync/team")
async def sync_team(
    body: SyncTeamRequest,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    """Sync all players for a specific team. Superuser only."""
    client = _get_client()
    try:
        result = await sync_service.sync_team(
            db, body.team_id, body.season, client, body.sleep_ms,
            created_by_user_id=current_user.id,
        )
        await db.commit()
        from app.stats import service as stats_service
        async with db.begin_nested():
            await stats_service.upsert_vendor_sync_state(db, VENDOR, success=True)
        await db.commit()
        return result
    except Exception as exc:
        await db.rollback()
        from app.stats import service as stats_service
        async with db.begin():
            await stats_service.upsert_vendor_sync_state(db, VENDOR, success=False, error=str(exc))
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))


@router.post("/sync/players/{player_id}")
async def sync_player(
    player_id: uuid.UUID,
    body: SyncPlayerRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Sync stats for one player. Requires player to have vendor_id set."""
    client = _get_client()
    try:
        result = await sync_service.sync_player_stats(db, player_id, body.season, body.league_id, client)
        await db.commit()
        return result
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))


@router.post("/compute-form")
async def compute_form(
    body: ComputeFormRequest,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    """Compute PlayerForm from existing snapshots. Superuser only."""
    count = await sync_service.compute_all_form(
        db, season=body.season, window_games=body.window_games
    )
    await db.commit()
    return {"players_updated": count}
