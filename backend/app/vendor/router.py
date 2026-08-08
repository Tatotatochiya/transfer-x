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


@router.get("/runs")
async def list_vendor_runs(
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List recent vendor sync runs (most recent first) — the per-run breakdown behind the summary in /status."""
    from app.stats import service as stats_service
    from app.stats.schemas import VendorSyncRunResponse

    runs = await stats_service.list_vendor_sync_runs(db, limit=min(limit, 200))
    user_ids = {r.triggered_by_user_id for r in runs if r.triggered_by_user_id}
    email_by_id = await stats_service.resolve_user_emails(db, user_ids)

    responses = []
    for r in runs:
        resp = VendorSyncRunResponse.model_validate(r)
        if r.triggered_by_user_id:
            resp.triggered_by_email = email_by_id.get(r.triggered_by_user_id)
        responses.append(resp)
    return responses


@router.post("/sync/league")
async def sync_league(
    body: SyncLeagueRequest,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    """Sync all players for a league. Superuser only."""
    client = _get_client()
    from app.stats import service as stats_service
    started_at = datetime.now(timezone.utc)
    params = body.model_dump()
    try:
        result = await sync_service.sync_league(
            db, body.league_id, body.season, client, body.sleep_ms,
            created_by_user_id=current_user.id,
        )
        await db.commit()
        # Record success
        async with db.begin_nested():
            await stats_service.upsert_vendor_sync_state(db, VENDOR, success=True)
            await stats_service.create_vendor_sync_run(
                db, vendor=VENDOR, operation="sync_league", params=params,
                success=True, result=result, error=None,
                triggered_by_user_id=current_user.id,
                started_at=started_at, finished_at=datetime.now(timezone.utc),
            )
        await db.commit()
        return result
    except Exception as exc:
        await db.rollback()
        async with db.begin():
            await stats_service.upsert_vendor_sync_state(db, VENDOR, success=False, error=str(exc))
            await stats_service.create_vendor_sync_run(
                db, vendor=VENDOR, operation="sync_league", params=params,
                success=False, result=None, error=str(exc),
                triggered_by_user_id=current_user.id,
                started_at=started_at, finished_at=datetime.now(timezone.utc),
            )
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))


@router.post("/sync/team")
async def sync_team(
    body: SyncTeamRequest,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    """Sync all players for a specific team. Superuser only."""
    client = _get_client()
    from app.stats import service as stats_service
    started_at = datetime.now(timezone.utc)
    params = body.model_dump()
    try:
        result = await sync_service.sync_team(
            db, body.team_id, body.season, client, body.sleep_ms,
            created_by_user_id=current_user.id,
        )
        await db.commit()
        async with db.begin_nested():
            await stats_service.upsert_vendor_sync_state(db, VENDOR, success=True)
            await stats_service.create_vendor_sync_run(
                db, vendor=VENDOR, operation="sync_team", params=params,
                success=True, result=result, error=None,
                triggered_by_user_id=current_user.id,
                started_at=started_at, finished_at=datetime.now(timezone.utc),
            )
        await db.commit()
        return result
    except Exception as exc:
        await db.rollback()
        async with db.begin():
            await stats_service.upsert_vendor_sync_state(db, VENDOR, success=False, error=str(exc))
            await stats_service.create_vendor_sync_run(
                db, vendor=VENDOR, operation="sync_team", params=params,
                success=False, result=None, error=str(exc),
                triggered_by_user_id=current_user.id,
                started_at=started_at, finished_at=datetime.now(timezone.utc),
            )
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
    from app.stats import service as stats_service
    started_at = datetime.now(timezone.utc)
    params = {"player_id": str(player_id), **body.model_dump()}
    try:
        result = await sync_service.sync_player_stats(db, player_id, body.season, body.league_id, client)
        await db.commit()
        async with db.begin_nested():
            await stats_service.create_vendor_sync_run(
                db, vendor=VENDOR, operation="sync_player", params=params,
                success=True, result=result, error=None,
                triggered_by_user_id=current_user.id,
                started_at=started_at, finished_at=datetime.now(timezone.utc),
            )
        await db.commit()
        return result
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:
        await db.rollback()
        async with db.begin():
            await stats_service.create_vendor_sync_run(
                db, vendor=VENDOR, operation="sync_player", params=params,
                success=False, result=None, error=str(exc),
                triggered_by_user_id=current_user.id,
                started_at=started_at, finished_at=datetime.now(timezone.utc),
            )
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))


@router.post("/compute-form")
async def compute_form(
    body: ComputeFormRequest,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    """Compute PlayerForm from existing snapshots. Superuser only. No external API calls made."""
    from app.stats import service as stats_service
    started_at = datetime.now(timezone.utc)
    params = body.model_dump()
    try:
        count = await sync_service.compute_all_form(
            db, season=body.season, window_games=body.window_games
        )
        result = {"players_updated": count}
        await db.commit()
        async with db.begin_nested():
            await stats_service.create_vendor_sync_run(
                db, vendor=VENDOR, operation="compute_form", params=params,
                success=True, result=result, error=None,
                triggered_by_user_id=current_user.id,
                started_at=started_at, finished_at=datetime.now(timezone.utc),
            )
        await db.commit()
        return result
    except Exception as exc:
        await db.rollback()
        async with db.begin():
            await stats_service.create_vendor_sync_run(
                db, vendor=VENDOR, operation="compute_form", params=params,
                success=False, result=None, error=str(exc),
                triggered_by_user_id=current_user.id,
                started_at=started_at, finished_at=datetime.now(timezone.utc),
            )
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
