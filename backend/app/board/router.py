from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.board import service
from app.board.schemas import BoardHistoryResponse, BoardResponse
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


@router.get("/board/history", response_model=BoardHistoryResponse)
async def get_board_history(
    side: Literal["BOTH", "BUYING", "SELLING"] = "BOTH",
    q: str | None = None,
    outcome: Literal["completed", "ended"] | None = None,
    page: int = 1,
    page_size: int = 30,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BoardHistoryResponse:
    """Every finished transfer and everything that went nowhere, newest
    first, searchable by player or club (what the old list pages showed)."""
    club, _ = await clubs_service.get_club_and_role_for_user(db, current_user.id)
    if club is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No club profile")
    return BoardHistoryResponse(**await service.get_history(
        db, club.id, side=side, q=q, outcome=outcome, page=page, page_size=min(max(page_size, 1), 100),
    ))
