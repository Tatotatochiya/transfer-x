"""M6 — Stats service layer."""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.stats.models import PlayerForm, PlayerStats, PlayerStatsSnapshot, VendorSyncRun, VendorSyncState


async def get_player_stats(
    db: AsyncSession,
    player_id: uuid.UUID,
    *,
    vendor: str | None = None,
    season: str | None = None,
) -> list[PlayerStats]:
    player_id = uuid.UUID(str(player_id))
    q = select(PlayerStats).where(PlayerStats.player_id == player_id).order_by(PlayerStats.updated_at.desc())
    if vendor is not None:
        q = q.where(PlayerStats.vendor == vendor)
    if season is not None:
        q = q.where(PlayerStats.season == season)
    result = await db.execute(q)
    return list(result.scalars())


async def upsert_player_stats(
    db: AsyncSession,
    player_id: uuid.UUID,
    vendor: str,
    league_id: str | None,
    season: str | None,
    *,
    goals: int = 0,
    assists: int = 0,
    appearances: int = 0,
    avg_rating: Decimal | None = None,
    form_score: Decimal | None = None,
) -> PlayerStats:
    player_id = uuid.UUID(str(player_id))
    q = select(PlayerStats).where(
        PlayerStats.player_id == player_id,
        PlayerStats.vendor == vendor,
    )
    if league_id is None:
        q = q.where(PlayerStats.league_id.is_(None))
    else:
        q = q.where(PlayerStats.league_id == league_id)
    if season is None:
        q = q.where(PlayerStats.season.is_(None))
    else:
        q = q.where(PlayerStats.season == season)

    result = await db.execute(q)
    existing = result.scalar_one_or_none()

    if existing:
        existing.goals = goals
        existing.assists = assists
        existing.appearances = appearances
        existing.avg_rating = avg_rating
        existing.form_score = form_score
        existing.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        await db.flush()
        return existing
    else:
        stats = PlayerStats(
            player_id=player_id,
            vendor=vendor,
            league_id=league_id,
            season=season,
            goals=goals,
            assists=assists,
            appearances=appearances,
            avg_rating=avg_rating,
            form_score=form_score,
        )
        db.add(stats)
        await db.flush()
        return stats


async def batch_get_form(
    db: AsyncSession,
    player_ids: list[uuid.UUID],
) -> dict[str, PlayerForm]:
    """Return a player_id → PlayerForm map for a list of player IDs (single query)."""
    if not player_ids:
        return {}
    coerced = [uuid.UUID(str(pid)) for pid in player_ids]
    result = await db.execute(select(PlayerForm).where(PlayerForm.player_id.in_(coerced)))
    return {str(form.player_id): form for form in result.scalars()}


async def batch_get_stats(
    db: AsyncSession,
    player_ids: list[uuid.UUID],
) -> dict[str, list[PlayerStats]]:
    """Return a player_id → [PlayerStats] map for a list of player IDs (single query)."""
    if not player_ids:
        return {}
    coerced = [uuid.UUID(str(pid)) for pid in player_ids]
    result = await db.execute(
        select(PlayerStats)
        .where(PlayerStats.player_id.in_(coerced))
        .order_by(PlayerStats.updated_at.desc())
    )
    by_player: dict[str, list[PlayerStats]] = {}
    for s in result.scalars():
        by_player.setdefault(str(s.player_id), []).append(s)
    return by_player


async def get_player_form(db: AsyncSession, player_id: uuid.UUID) -> PlayerForm | None:
    player_id = uuid.UUID(str(player_id))
    result = await db.execute(select(PlayerForm).where(PlayerForm.player_id == player_id))
    return result.scalar_one_or_none()


async def upsert_player_form(
    db: AsyncSession,
    player_id: uuid.UUID,
    form_score: Decimal,
    games_considered: int,
    key_metrics: dict | None,
) -> PlayerForm:
    player_id = uuid.UUID(str(player_id))
    existing = await get_player_form(db, player_id)
    if existing:
        existing.form_score = form_score
        existing.games_considered = games_considered
        existing.key_metrics = key_metrics
        existing.last_updated = datetime.now(timezone.utc).replace(tzinfo=None)
        await db.flush()
        return existing
    else:
        form = PlayerForm(
            player_id=player_id,
            form_score=form_score,
            games_considered=games_considered,
            key_metrics=key_metrics,
        )
        db.add(form)
        await db.flush()
        return form


async def list_snapshots(
    db: AsyncSession,
    player_id: uuid.UUID,
    *,
    vendor: str | None = None,
    limit: int = 20,
) -> list[PlayerStatsSnapshot]:
    player_id = uuid.UUID(str(player_id))
    q = (
        select(PlayerStatsSnapshot)
        .where(PlayerStatsSnapshot.player_id == player_id)
        .order_by(PlayerStatsSnapshot.fetched_at.desc())
        .limit(limit)
    )
    if vendor is not None:
        q = q.where(PlayerStatsSnapshot.vendor == vendor)
    result = await db.execute(q)
    return list(result.scalars())


async def create_snapshot(
    db: AsyncSession,
    player_id: uuid.UUID,
    vendor: str,
    payload: dict,
) -> PlayerStatsSnapshot:
    player_id = uuid.UUID(str(player_id))
    snapshot = PlayerStatsSnapshot(player_id=player_id, vendor=vendor, payload=payload)
    db.add(snapshot)
    await db.flush()
    return snapshot


async def list_vendor_sync_states(db: AsyncSession) -> list[VendorSyncState]:
    result = await db.execute(select(VendorSyncState).order_by(VendorSyncState.vendor))
    return list(result.scalars())


async def upsert_vendor_sync_state(
    db: AsyncSession,
    vendor: str,
    *,
    success: bool,
    error: str | None = None,
) -> VendorSyncState:
    result = await db.execute(select(VendorSyncState).where(VendorSyncState.vendor == vendor))
    existing = result.scalar_one_or_none()
    now = datetime.now(timezone.utc).replace(tzinfo=None)  # naive UTC — matches vendor_sync_states columns

    if existing:
        existing.last_sync_at = now
        if success:
            existing.last_success_at = now
            existing.last_error = None
            existing.error_count = 0
        else:
            existing.last_error = error
            existing.error_count = (existing.error_count or 0) + 1
        await db.flush()
        return existing
    else:
        state = VendorSyncState(
            vendor=vendor,
            last_sync_at=now,
            last_success_at=now if success else None,
            last_error=None if success else error,
            error_count=0 if success else 1,
        )
        db.add(state)
        await db.flush()
        return state


async def create_vendor_sync_run(
    db: AsyncSession,
    *,
    vendor: str,
    operation: str,
    params: dict | None,
    success: bool,
    result: dict | None,
    error: str | None,
    triggered_by_user_id: uuid.UUID | None,
    started_at: datetime,
    finished_at: datetime,
) -> VendorSyncRun:
    run = VendorSyncRun(
        vendor=vendor,
        operation=operation,
        params=params,
        success=success,
        result=result,
        error=error,
        triggered_by_user_id=triggered_by_user_id,
        started_at=started_at,
        finished_at=finished_at,
        duration_ms=int((finished_at - started_at).total_seconds() * 1000),
    )
    db.add(run)
    await db.flush()
    return run


async def list_vendor_sync_runs(
    db: AsyncSession, *, vendor: str | None = None, limit: int = 50
) -> list[VendorSyncRun]:
    q = select(VendorSyncRun).order_by(VendorSyncRun.started_at.desc()).limit(limit)
    if vendor:
        q = q.where(VendorSyncRun.vendor == vendor)
    result = await db.execute(q)
    return list(result.scalars())


async def resolve_user_emails(db: AsyncSession, user_ids: set[uuid.UUID]) -> dict[uuid.UUID, str]:
    """Bulk-resolve user ids to emails, for labeling who triggered a sync run."""
    if not user_ids:
        return {}
    from app.auth.models import User
    result = await db.execute(select(User.id, User.email).where(User.id.in_(user_ids)))
    return {row.id: row.email for row in result}
