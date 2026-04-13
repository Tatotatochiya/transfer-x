"""M6 — Stats endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.database import get_db
from app.deps import get_current_user, get_optional_user
from app.players import service as players_service
from app.stats import service
from app.stats.schemas import (
    PlayerFormResponse,
    PlayerFormUpsertRequest,
    PlayerStatsResponse,
    PlayerStatsUpsertRequest,
    SnapshotCreateRequest,
    SnapshotResponse,
    VendorSyncStateResponse,
    VendorSyncStateUpsertRequest,
)

router = APIRouter(tags=["stats"])


async def _get_player_or_404(db: AsyncSession, player_id: uuid.UUID):
    player = await players_service.get_player_by_id(db, player_id)
    if player is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Player not found")
    return player


# ── Batch endpoints (must be declared before parameterised routes) ─────────────


@router.get("/players/stats/batch", response_model=dict[str, list[PlayerStatsResponse]])
async def batch_get_player_stats(
    player_ids: str = Query(..., description="Comma-separated player UUIDs"),
    db: AsyncSession = Depends(get_db),
):
    """Return stats for multiple players in a single DB query."""
    try:
        ids = [uuid.UUID(i.strip()) for i in player_ids.split(",") if i.strip()]
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid UUID in player_ids")
    if not ids:
        return {}
    results = await service.batch_get_stats(db, ids)
    return {k: [PlayerStatsResponse.model_validate(s) for s in v] for k, v in results.items()}


@router.get("/players/form/batch", response_model=dict[str, PlayerFormResponse])
async def batch_get_player_form(
    player_ids: str = Query(..., description="Comma-separated player UUIDs"),
    db: AsyncSession = Depends(get_db),
):
    """Return form scores for multiple players in a single DB query."""
    try:
        ids = [uuid.UUID(i.strip()) for i in player_ids.split(",") if i.strip()]
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid UUID in player_ids")
    if not ids:
        return {}
    results = await service.batch_get_form(db, ids)
    return {k: PlayerFormResponse.model_validate(v) for k, v in results.items()}


# ── Player Stats ──────────────────────────────────────────────────────────────


@router.get("/players/{player_id}/stats", response_model=list[PlayerStatsResponse])
async def get_player_stats(
    player_id: uuid.UUID,
    vendor: str | None = None,
    season: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
):
    await _get_player_or_404(db, player_id)
    stats = await service.get_player_stats(db, player_id, vendor=vendor, season=season)
    return [PlayerStatsResponse.model_validate(s) for s in stats]


@router.put("/players/{player_id}/stats", response_model=PlayerStatsResponse)
async def upsert_player_stats(
    player_id: uuid.UUID,
    body: PlayerStatsUpsertRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _get_player_or_404(db, player_id)
    stats = await service.upsert_player_stats(
        db,
        player_id,
        body.vendor,
        body.league_id,
        body.season,
        goals=body.goals,
        assists=body.assists,
        appearances=body.appearances,
        avg_rating=body.avg_rating,
        form_score=body.form_score,
    )
    await db.commit()
    await db.refresh(stats)
    return PlayerStatsResponse.model_validate(stats)


# ── Player Form ───────────────────────────────────────────────────────────────


@router.get("/players/{player_id}/form", response_model=PlayerFormResponse)
async def get_player_form(
    player_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
):
    await _get_player_or_404(db, player_id)
    form = await service.get_player_form(db, player_id)
    if form is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No form data for this player")
    return PlayerFormResponse.model_validate(form)


@router.put("/players/{player_id}/form", response_model=PlayerFormResponse)
async def upsert_player_form(
    player_id: uuid.UUID,
    body: PlayerFormUpsertRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _get_player_or_404(db, player_id)
    form = await service.upsert_player_form(
        db, player_id, body.form_score, body.games_considered, body.key_metrics
    )
    await db.commit()
    await db.refresh(form)
    return PlayerFormResponse.model_validate(form)


# ── Snapshots ────────────────────────────────────────────────────────────────


@router.get("/players/{player_id}/snapshots", response_model=list[SnapshotResponse])
async def list_snapshots(
    player_id: uuid.UUID,
    vendor: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _get_player_or_404(db, player_id)
    snapshots = await service.list_snapshots(db, player_id, vendor=vendor, limit=limit)
    return [SnapshotResponse.model_validate(s) for s in snapshots]


@router.post("/players/{player_id}/snapshots", response_model=SnapshotResponse, status_code=status.HTTP_201_CREATED)
async def create_snapshot(
    player_id: uuid.UUID,
    body: SnapshotCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _get_player_or_404(db, player_id)
    snapshot = await service.create_snapshot(db, player_id, body.vendor, body.payload)
    await db.commit()
    await db.refresh(snapshot)
    return SnapshotResponse.model_validate(snapshot)


# ── Vendor Sync States ────────────────────────────────────────────────────────


@router.get("/stats/sync-states", response_model=list[VendorSyncStateResponse])
async def list_vendor_sync_states(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    states = await service.list_vendor_sync_states(db)
    return [VendorSyncStateResponse.model_validate(s) for s in states]


@router.put("/stats/sync-states/{vendor}", response_model=VendorSyncStateResponse)
async def upsert_vendor_sync_state(
    vendor: str,
    body: VendorSyncStateUpsertRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    state = await service.upsert_vendor_sync_state(db, vendor, success=body.success, error=body.error)
    await db.commit()
    await db.refresh(state)
    return VendorSyncStateResponse.model_validate(state)
