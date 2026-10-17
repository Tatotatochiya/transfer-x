"""Deadline-day mode (deadline/service.py)."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.clubs import service as clubs_service
from app.database import get_db
from app.deadline import service

router = APIRouter(tags=["deadline"])


@router.get("/deadline")
async def get_deadline(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """The club's open transfers against the window's close: what each is
    waiting on, whose move it is, and which are at risk. For the club's own
    people; the same masking as the Transfers board."""
    club, _ = await clubs_service.get_club_and_role_for_user(db, current_user.id)
    if club is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No club profile")
    return await service.board(db, club.id)
