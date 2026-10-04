from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.board import service
from app.board.schemas import BoardResponse
from app.clubs import service as clubs_service
from app.database import get_db

router = APIRouter(tags=["board"])


@router.get("/board", response_model=BoardResponse)
async def get_board(
    side: Literal["BOTH", "BUYING", "SELLING"] = "BOTH",
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BoardResponse:
    """The Transfers board: every player the club is buying or selling, once,
    at its furthest point (product ADR 0008). For the club's own people."""
    club, _ = await clubs_service.get_club_and_role_for_user(db, current_user.id)
    if club is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No club profile")
    return await service.get_board(db, club.id, side)
