"""Enquiries endpoints. Every route is scoped to the caller's club; a club
that is not a party gets 404, not 403."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.clubs import service as clubs_service
from app.clubs.capabilities import Capability, require_club_capability
from app.database import get_db
from app.deps import get_current_user
from app.enquiries import service
from app.enquiries.schemas import EnquiryCreateRequest, EnquiryMessageRequest, EnquiryResponse

router = APIRouter(tags=["enquiries"])

# Asking about or answering for a player is a market action, like an offer.
_market_write = require_club_capability(Capability.MARKET_WRITE)


async def _club(db: AsyncSession, user: User):
    club = await clubs_service.get_club_for_user(db, user.id)
    if club is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No club profile found")
    return club


async def _enquiry_for(db: AsyncSession, enquiry_id: uuid.UUID, club_id: uuid.UUID):
    enquiry = await service.get_enquiry(db, enquiry_id)
    if enquiry is None or club_id not in (enquiry.from_club_id, enquiry.to_club_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Enquiry not found")
    return enquiry


@router.post("/enquiries", response_model=EnquiryResponse, status_code=status.HTTP_201_CREATED)
async def create_enquiry(
    body: EnquiryCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _write: User = Depends(_market_write),
):
    club = await _club(db, current_user)
    try:
        enquiry = await service.create_enquiry(
            db, player_id=body.player_id, from_club_id=club.id, body=body.body,
            is_anonymous=body.is_anonymous, actor_user_id=current_user.id,
        )
        await db.commit()
    except FileExistsError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": "You already have an open enquiry about him.", "enquiry_id": str(exc)},
        )
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    enquiry = await service.get_enquiry(db, enquiry.id)
    return service.to_response(enquiry, club.id, with_messages=True)


@router.get("/enquiries", response_model=list[EnquiryResponse])
async def list_enquiries(
    box: str | None = Query(None, pattern="^(received|sent)$"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    club = await _club(db, current_user)
    return [service.to_response(e, club.id, with_messages=False) for e in await service.list_enquiries(db, club.id, box=box)]


@router.get("/enquiries/{enquiry_id}", response_model=EnquiryResponse)
async def get_enquiry(
    enquiry_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    club = await _club(db, current_user)
    enquiry = await _enquiry_for(db, enquiry_id, club.id)
    return service.to_response(enquiry, club.id, with_messages=True)


@router.post("/enquiries/{enquiry_id}/messages", response_model=EnquiryResponse)
async def reply(
    enquiry_id: uuid.UUID,
    body: EnquiryMessageRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _write: User = Depends(_market_write),
):
    club = await _club(db, current_user)
    enquiry = await _enquiry_for(db, enquiry_id, club.id)
    try:
        await service.add_message(db, enquiry, sender_club_id=club.id, body=body.body, actor_user_id=current_user.id)
        await db.commit()
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    db.expire(enquiry)
    enquiry = await service.get_enquiry(db, enquiry_id)
    return service.to_response(enquiry, club.id, with_messages=True)


@router.post("/enquiries/{enquiry_id}/close", response_model=EnquiryResponse)
async def close(
    enquiry_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _write: User = Depends(_market_write),
):
    club = await _club(db, current_user)
    enquiry = await _enquiry_for(db, enquiry_id, club.id)
    try:
        await service.close_enquiry(db, enquiry, club_id=club.id, actor_user_id=current_user.id)
        await db.commit()
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    # Reload: the commit expired server-set columns (updated_at).
    db.expire(enquiry)
    enquiry = await service.get_enquiry(db, enquiry_id)
    return service.to_response(enquiry, club.id, with_messages=True)
