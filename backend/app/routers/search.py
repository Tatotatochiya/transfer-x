"""Global search — players and clubs in a single query."""

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.clubs.models import Club
from app.clubs.schemas import ClubPublicResponse
from app.database import get_db
from app.players.models import Player, PlayerVisibility
from app.players.schemas import PlayerResponse

router = APIRouter(prefix="/search", tags=["search"])


class SearchResults(BaseModel):
    players: list[PlayerResponse]
    clubs: list[ClubPublicResponse]


@router.get("", response_model=SearchResults)
async def search(
    q: str = Query(..., min_length=2, max_length=100),
    db: AsyncSession = Depends(get_db),
) -> SearchResults:
    term = f"%{q.strip()}%"

    player_rows = await db.execute(
        select(Player)
        .where(Player.name.ilike(term))
        .where(Player.visibility.in_([PlayerVisibility.PUBLIC, PlayerVisibility.CLUBS_ONLY]))
        .options(selectinload(Player.current_club), selectinload(Player.world_team))
        .order_by(Player.name)
        .limit(8)
    )

    club_rows = await db.execute(
        select(Club)
        .where(Club.name.ilike(term))
        .order_by(Club.name)
        .limit(5)
    )

    return SearchResults(
        players=[PlayerResponse.model_validate(p) for p in player_rows.scalars()],
        clubs=[ClubPublicResponse.model_validate(c) for c in club_rows.scalars()],
    )
