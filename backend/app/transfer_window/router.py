"""Transfer window endpoints."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_superuser, get_optional_user
from app.transfer_window import service
from app.transfer_window.schemas import (
    TransferWindowCreate,
    TransferWindowResponse,
    TransferWindowStatus,
    WindowCoverage,
)

from app.admin.schemas import AdminReasonRequest  # noqa: E402

router = APIRouter(prefix="/transfers/window", tags=["transfer-window"])


def _to_response(w) -> TransferWindowResponse:
    return TransferWindowResponse(
        id=w.id,
        name=w.name,
        country=w.country,
        opens_at=w.opens_at,
        closes_at=w.closes_at,
        source_url=w.source_url,
        checked_on=w.checked_on,
        is_open=service._window_is_open(w),
        created_at=w.created_at,
    )


@router.get("/status", response_model=TransferWindowStatus)
async def get_window_status(
    country: str | None = Query(None, max_length=100),
    db: AsyncSession = Depends(get_db),
    user=Depends(get_optional_user),
):
    """Public. The windows of the signed-in user's club's country, else of
    `country`, else the ones with no country."""
    if user is not None and country is None:
        from app.clubs.service import get_club_for_user

        club = await get_club_for_user(db, user.id)
        country = club.country if club is not None else None
    enforced = await service.any_window_exists(db, country)
    current = await service.get_current_window(db, country)
    nxt = await service.get_next_window(db, country) if not current else None
    return TransferWindowStatus(
        enforced=enforced,
        is_open=current is not None,
        country=country,
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


@router.get("/coverage", response_model=list[WindowCoverage])
async def window_coverage(
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_superuser),
):
    """Each country with clubs on TransferX, and whether its windows are set
    up for the next six months."""
    return [
        WindowCoverage(
            country=row["country"], own_windows=row["own_windows"], missing=row["missing"],
            current_window=_to_response(row["current"]) if row["current"] else None,
            next_window=_to_response(row["next"]) if row["next"] else None,
        )
        for row in await service.coverage(db)
    ]


@router.post("", response_model=TransferWindowResponse, status_code=status.HTTP_201_CREATED)
async def create_window(
    body: TransferWindowCreate,
    db: AsyncSession = Depends(get_db),
    admin=Depends(get_current_superuser),
):
    from app.admin.audit import record

    w = await service.create_window(db, name=body.name, opens_at=body.opens_at, closes_at=body.closes_at,
                                    country=body.country, source_url=body.source_url, checked_on=body.checked_on)
    await record(db, admin, "transfer_window.created", entity_type="transfer_window", entity_id=w.id,
                 description=f"Created the transfer window {body.name}",
                 details={"country": w.country, "opens_at": body.opens_at, "closes_at": body.closes_at,
                          "source_url": w.source_url, "checked_on": body.checked_on})
    await db.commit()
    await db.refresh(w)
    return _to_response(w)


@router.delete("/{window_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_window(
    window_id: uuid.UUID,
    body: AdminReasonRequest,
    db: AsyncSession = Depends(get_db),
    admin=Depends(get_current_superuser),
):
    """Deleting a window changes when clubs can complete transfers, so it
    needs a reason, which goes in the audit trail."""
    from app.admin.audit import record

    deleted = await service.delete_window(db, window_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Window not found")
    await record(db, admin, "transfer_window.deleted", entity_type="transfer_window", entity_id=window_id,
                 description="Deleted a transfer window", reason=body.reason)
    await db.commit()
