"""M5 — Scouting endpoints."""

import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.models import User
from app.clubs import service as clubs_service
from app.database import get_db
from app.deps import get_current_user
from app.scouting import service
from app.scouting.schemas import (
    InterestUpsertRequest,
    PlayerInterestResponse,
    ShortlistCreateRequest,
    ShortlistItemRequest,
    ShortlistItemResponse,
    ShortlistItemUpdateRequest,
    ShortlistResponse,
    ShortlistSummaryResponse,
    ShortlistUpdateRequest,
    TargetPlayerResponse,
)

router = APIRouter(prefix="/scouting", tags=["scouting"])


async def _get_club_or_403(db: AsyncSession, user: User):
    club = await clubs_service.get_club_by_user_id(db, user.id)
    if club is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No club profile")
    return club


async def _get_shortlist_or_404(db: AsyncSession, shortlist_id: uuid.UUID, club_id: uuid.UUID):
    sl = await service.get_shortlist_by_id(db, shortlist_id)
    if sl is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shortlist not found")
    if sl.club_id != club_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your shortlist")
    return sl


# ── Shortlists ────────────────────────────────────────────────────────────────


@router.get("/shortlists", response_model=list[ShortlistSummaryResponse])
async def list_shortlists(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    club = await _get_club_or_403(db, current_user)
    shortlists = await service.list_shortlists(db, club.id)
    return [
        ShortlistSummaryResponse(
            id=sl.id,
            club_id=sl.club_id,
            name=sl.name,
            description=sl.description,
            item_count=len(sl.items),
            created_at=sl.created_at,
            updated_at=sl.updated_at,
        )
        for sl in shortlists
    ]


@router.post("/shortlists", response_model=ShortlistResponse, status_code=status.HTTP_201_CREATED)
async def create_shortlist(
    body: ShortlistCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    club = await _get_club_or_403(db, current_user)
    try:
        sl = await service.create_shortlist(db, club_id=club.id, name=body.name, description=body.description)
        await db.commit()
        await db.refresh(sl)
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    sl = await service.get_shortlist_by_id(db, sl.id)
    return ShortlistResponse.model_validate(sl)


@router.get("/shortlists/{shortlist_id}", response_model=ShortlistResponse)
async def get_shortlist(
    shortlist_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    club = await _get_club_or_403(db, current_user)
    sl = await _get_shortlist_or_404(db, shortlist_id, club.id)
    return ShortlistResponse.model_validate(sl)


@router.patch("/shortlists/{shortlist_id}", response_model=ShortlistResponse)
async def update_shortlist(
    shortlist_id: uuid.UUID,
    body: ShortlistUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    club = await _get_club_or_403(db, current_user)
    sl = await _get_shortlist_or_404(db, shortlist_id, club.id)
    try:
        await service.update_shortlist(db, sl, name=body.name, description=body.description)
        await db.commit()
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    sl = await service.get_shortlist_by_id(db, shortlist_id)
    return ShortlistResponse.model_validate(sl)


@router.delete("/shortlists/{shortlist_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_shortlist(
    shortlist_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    club = await _get_club_or_403(db, current_user)
    sl = await _get_shortlist_or_404(db, shortlist_id, club.id)
    await service.delete_shortlist(db, sl)
    await db.commit()


# ── Shortlist items ───────────────────────────────────────────────────────────


@router.post(
    "/shortlists/{shortlist_id}/items",
    response_model=ShortlistItemResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_to_shortlist(
    shortlist_id: uuid.UUID,
    body: ShortlistItemRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    club = await _get_club_or_403(db, current_user)
    sl = await _get_shortlist_or_404(db, shortlist_id, club.id)
    try:
        item = await service.add_to_shortlist(
            db, shortlist_id=sl.id, player_id=body.player_id, priority=body.priority, notes=body.notes
        )
        await db.commit()
        await db.refresh(item)
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    item = await service.get_shortlist_item(db, shortlist_id, body.player_id)
    return ShortlistItemResponse.model_validate(item)


@router.patch(
    "/shortlists/{shortlist_id}/items/{player_id}",
    response_model=ShortlistItemResponse,
)
async def update_shortlist_item(
    shortlist_id: uuid.UUID,
    player_id: uuid.UUID,
    body: ShortlistItemUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    club = await _get_club_or_403(db, current_user)
    await _get_shortlist_or_404(db, shortlist_id, club.id)
    item = await service.get_shortlist_item(db, shortlist_id, player_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Player not on shortlist")
    try:
        await service.update_shortlist_item(db, item, priority=body.priority, notes=body.notes)
        await db.commit()
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    item = await service.get_shortlist_item(db, shortlist_id, player_id)
    return ShortlistItemResponse.model_validate(item)


@router.delete(
    "/shortlists/{shortlist_id}/items/{player_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_from_shortlist(
    shortlist_id: uuid.UUID,
    player_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    club = await _get_club_or_403(db, current_user)
    await _get_shortlist_or_404(db, shortlist_id, club.id)
    item = await service.get_shortlist_item(db, shortlist_id, player_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Player not on shortlist")
    await service.remove_from_shortlist(db, item)
    await db.commit()


# ── Player interests ──────────────────────────────────────────────────────────


@router.get("/interests", response_model=list[PlayerInterestResponse])
async def list_interests(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    club = await _get_club_or_403(db, current_user)
    interests = await service.list_interests(db, club.id)
    return [PlayerInterestResponse.model_validate(i) for i in interests]


@router.put("/interests/{player_id}", response_model=PlayerInterestResponse)
async def set_interest(
    player_id: uuid.UUID,
    body: InterestUpsertRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    club = await _get_club_or_403(db, current_user)
    interest = await service.set_interest(
        db,
        club_id=club.id,
        player_id=player_id,
        level=body.level,
        stage=body.stage,
        notes=body.notes,
    )
    await db.commit()
    interest = await service.get_interest(db, club.id, player_id)
    return PlayerInterestResponse.model_validate(interest)


@router.delete("/interests/{player_id}", status_code=status.HTTP_204_NO_CONTENT)
async def clear_interest(
    player_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    club = await _get_club_or_403(db, current_user)
    interest = await service.get_interest(db, club.id, player_id)
    if interest is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No interest record found")
    await service.clear_interest(db, interest)
    await db.commit()


# ── Targets dashboard ─────────────────────────────────────────────────────────


@router.get("/targets", response_model=list[TargetPlayerResponse])
async def get_targets(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    club = await _get_club_or_403(db, current_user)
    targets = await service.get_targets(db, club.id)
    return [TargetPlayerResponse(**t) for t in targets]


# ── Shortlist market hits ─────────────────────────────────────────────────────

class ShortlistHit(BaseModel):
    player_id: str
    player_name: str
    position: str | None
    shortlist_name: str
    sale_id: str
    sale_type: str
    asking_price: Decimal | None
    deadline: datetime | None


@router.get("/market-hits", response_model=list[ShortlistHit])
async def get_market_hits(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Players on this club's shortlists that currently have an open sale."""
    from app.scouting.models import Shortlist, ShortlistItem
    from app.sales.models import Sale, SaleStatus
    from app.players.models import Player

    club = await _get_club_or_403(db, current_user)

    result = await db.execute(
        select(
            Player.id,
            Player.name,
            Player.position,
            Shortlist.name.label("shortlist_name"),
            Sale.id.label("sale_id"),
            Sale.sale_type,
            Sale.asking_price,
            Sale.deadline,
        )
        .join(ShortlistItem, ShortlistItem.player_id == Player.id)
        .join(Shortlist, Shortlist.id == ShortlistItem.shortlist_id)
        .join(Sale, Sale.player_id == Player.id)
        .where(
            Shortlist.club_id == club.id,
            Sale.status == SaleStatus.OPEN,
        )
        .distinct()
    )
    rows = result.all()
    return [
        ShortlistHit(
            player_id=str(row.id),
            player_name=row.name,
            position=row.position,
            shortlist_name=row.shortlist_name,
            sale_id=str(row.sale_id),
            sale_type=row.sale_type,
            asking_price=row.asking_price,
            deadline=row.deadline,
        )
        for row in rows
    ]
