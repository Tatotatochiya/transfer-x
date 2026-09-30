"""Lite mode routes (docs/feature_spec/lite-mode)."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.database import get_db
from app.deps import get_current_user
from app.lite import service
from app.lite.schemas import (
    LiteHomeResponse,
    LiteResumeRequest,
    PreferencesResponse,
    PreferencesUpdateRequest,
)

router = APIRouter(tags=["lite"])


@router.get("/users/me/preferences", response_model=PreferencesResponse)
async def get_my_preferences(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await service.get_preferences(db, current_user)


@router.patch("/users/me/preferences", response_model=PreferencesResponse)
async def update_my_preferences(
    body: PreferencesUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    prefs = await service.update_preferences(
        db, current_user, lite_mode=body.lite_mode, text_scale=body.text_scale,
    )
    await db.commit()
    return prefs


# ── Lite home (BACKEND.md §2) ────────────────────────────────────────────────


@router.get("/lite/home", response_model=LiteHomeResponse)
async def lite_home(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Everything the Lite home shows, in one request. Never calls a model."""
    try:
        return await service.lite_home(db, current_user)
    except LookupError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lite mode is for club members")


@router.put("/lite/resume", status_code=status.HTTP_204_NO_CONTENT)
async def set_resume(
    body: LiteResumeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Remember the unfinished Lite flow, for "Carry on where you left off"."""
    try:
        await service.set_resume(db, current_user, title=body.title, href=body.href)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    await db.commit()


@router.delete("/lite/resume", status_code=status.HTTP_204_NO_CONTENT)
async def clear_resume(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await service.clear_resume(db, current_user)
    await db.commit()


# ── Buy flow (BACKEND.md §2a) ────────────────────────────────────────────────


@router.get("/lite/buy/squad")
async def buy_squad_counts(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """How many players the club has in each position, for "You have none"."""
    from app.clubs.service import get_club_and_role_for_user

    club, _ = await get_club_and_role_for_user(db, current_user.id)
    if club is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lite mode is for club members")
    return {"counts": await service.squad_counts(db, club.id)}


@router.get("/lite/buy/candidates")
async def buy_candidates(
    position: str,
    band: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Three players the club could make an offer for now, picked by TransferX
    (decision 3). The model only rewords the reasons when it can."""
    try:
        return await service.buy_candidates(db, current_user, position=position, band=band)
    except LookupError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lite mode is for club members")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))


# ── Action cards (L4, README "Screen 5") ─────────────────────────────────────


@router.get("/lite/offer-draft")
async def offer_draft(
    player_id: uuid.UUID = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """What a new bid's card starts from. Describes only: confirming the card
    calls POST /offers, and its money panel is POST /ai/offer-check."""
    try:
        return await service.offer_draft(db, current_user, player_id=player_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


@router.get("/lite/offers/{offer_id}")
async def offer_card(
    offer_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """An offer the club is party to, as an action card (anonymous buyers
    masked). Accept, counter and reject go to the existing offer endpoints."""
    try:
        return await service.offer_card(db, current_user, offer_id=offer_id)
    except LookupError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Offer not found")
