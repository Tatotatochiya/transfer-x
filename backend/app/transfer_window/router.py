"""Transfer window endpoints."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_superuser
from app.transfer_window import service
from app.transfer_window.schemas import TransferWindowCreate, TransferWindowResponse, TransferWindowStatus

router = APIRouter(prefix="/transfers/window", tags=["transfer-window"])


def _to_response(w) -> TransferWindowResponse:
    return TransferWindowResponse(
        id=w.id,
        name=w.name,
        association=w.association,
        opens_at=w.opens_at,
        closes_at=w.closes_at,
        is_open=service._window_is_open(w),
        created_at=w.created_at,
    )


@router.get("/status", response_model=TransferWindowStatus)
async def get_window_status(db: AsyncSession = Depends(get_db)):
    """Public — returns current window state."""
    enforced = await service.any_window_exists(db)
    current = await service.get_current_window(db)
    nxt = await service.get_next_window(db) if not current else None
    return TransferWindowStatus(
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
    w = await service.create_window(db, name=body.name, opens_at=body.opens_at, closes_at=body.closes_at, association=body.association)
    await db.commit()
    await db.refresh(w)
    return _to_response(w)


@router.delete("/{window_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_window(
    window_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_superuser),
):
    deleted = await service.delete_window(db, window_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Window not found")
    await db.commit()
