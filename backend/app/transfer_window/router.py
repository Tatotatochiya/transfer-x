"""Transfer window endpoints."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_superuser
from app.transfer_window import service
from app.transfer_window.schemas import (
    TransferWindowCreate,
    TransferWindowResponse,
    TransferWindowStatus,
    TransferWindowUpdate,
)

router = APIRouter(prefix="/transfers/window", tags=["transfer-window"])


def _to_response(w) -> TransferWindowResponse:
    return TransferWindowResponse(
        id=w.id,
        name=w.name,
        association=w.association,
        opens_at=w.opens_at,
        closes_at=w.closes_at,
        grace_period_hours=w.grace_period_hours,
        is_open=service._window_is_open(w),
        created_at=w.created_at,
    )


@router.get("/status", response_model=TransferWindowStatus)
async def get_window_status(
    association: str | None = Query(None, description="Resolve status for this association (e.g. a club's country); omit for global-only windows."),
    db: AsyncSession = Depends(get_db),
):
    """Public — returns current window state for the given association (or global-only if omitted)."""
    enforced = await service.has_applicable_windows(db, association=association)
    current = await service.get_current_window(db, association=association)
    nxt = await service.get_next_window(db, association=association) if not current else None
    return TransferWindowStatus(
        association=association,
        enforced=enforced,
        is_open=current is not None,
        current_window=_to_response(current) if current else None,
        next_window=_to_response(nxt) if nxt else None,
    )


@router.get("", response_model=list[TransferWindowResponse])
async def list_windows(
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_superuser),
):
    windows = await service.list_windows(db)
    return [_to_response(w) for w in windows]


@router.post("", response_model=TransferWindowResponse, status_code=status.HTTP_201_CREATED)
async def create_window(
    body: TransferWindowCreate,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_superuser),
):
    w = await service.create_window(
        db, name=body.name, opens_at=body.opens_at, closes_at=body.closes_at,
        association=body.association, grace_period_hours=body.grace_period_hours,
    )
    await db.commit()
    await db.refresh(w)
    return _to_response(w)


@router.patch("/{window_id}", response_model=TransferWindowResponse)
async def update_window(
    window_id: uuid.UUID,
    body: TransferWindowUpdate,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_superuser),
):
    """Admin override — edit an existing window's name/association/dates/grace period in place."""
    updates = body.model_dump(exclude_unset=True)
    try:
        w = await service.update_window(db, window_id, updates)
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    if w is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Window not found")
    await db.commit()
    await db.refresh(w)
    return _to_response(w)


@router.delete("/{window_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_window(
    window_id: uuid.UUID,
    reason: str = Query(..., description="Required — recorded in the audit trail."),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_superuser),
):
    try:
        deleted = await service.delete_window(
            db, window_id, reason=reason, actor_user_id=current_user.id,
        )
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Window not found")
    await db.commit()
