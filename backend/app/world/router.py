"""M6 — World endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import or_

from app.auth.models import User
from app.common.schemas import Paginated
from app.database import get_db
from app.deps import get_current_user, get_optional_user
from app.fixtures.models import Fixture
from app.players.schemas import PlayerResponse
from app.players import service as players_service
from app.vendor.client import VENDOR
from app.world import service
from app.world.schemas import LeagueCreateRequest, LeagueResponse, WorldTeamResponse

router = APIRouter(prefix="/world", tags=["world"])


# ── World teams ───────────────────────────────────────────────────────────────

@router.get("/teams", response_model=Paginated[WorldTeamResponse])
async def list_world_teams(
    search: str | None = None,
    country: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    teams, total = await service.list_world_teams(
        db, search=search, country=country, page=page, page_size=page_size
    )
    return Paginated(
        items=[WorldTeamResponse.model_validate(t) for t in teams],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/teams/by-vendor/{vendor_id}", response_model=WorldTeamResponse)
async def get_world_team_by_vendor(
    vendor_id: str,
    vendor: str = Query(default="api-football"),
    db: AsyncSession = Depends(get_db),
):
    team = await service.get_world_team_by_vendor_id(db, vendor=vendor, vendor_id=vendor_id)
    if team is not None:
        return WorldTeamResponse.model_validate(team)

    # Not yet in world_teams — try to bootstrap it from cached fixture data
    try:
        int_vendor_id = int(vendor_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")

    result = await db.execute(
        select(Fixture).where(
            or_(
                Fixture.home_team_vendor_id == int_vendor_id,
                Fixture.away_team_vendor_id == int_vendor_id,
            )
        ).limit(1)
    )
    fixture = result.scalar_one_or_none()
    if fixture is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")

    if fixture.home_team_vendor_id == int_vendor_id:
        name = fixture.home_team_name
        crest_url = fixture.home_team_crest_url
    else:
        name = fixture.away_team_name
        crest_url = fixture.away_team_crest_url

    team = await service.upsert_world_team(
        db,
        vendor=VENDOR,
        vendor_id=vendor_id,
        name=name,
        crest_url=crest_url,
        league_name=fixture.league_name,
    )
    await db.commit()
    await db.refresh(team)
    return WorldTeamResponse.model_validate(team)


@router.get("/teams/{team_id}", response_model=WorldTeamResponse)
async def get_world_team(
    team_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    team = await service.get_world_team_by_id(db, team_id)
    if team is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")
    return WorldTeamResponse.model_validate(team)


@router.get("/teams/{team_id}/players", response_model=Paginated[PlayerResponse])
async def get_world_team_players(
    team_id: uuid.UUID,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
):
    team = await service.get_world_team_by_id(db, team_id)
    if team is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")
    players, total = await players_service.list_world_team_squad(
        db, team_id=team_id, page=page, page_size=page_size
    )
    return Paginated(
        items=[PlayerResponse.model_validate(p) for p in players],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/leagues", response_model=list[LeagueResponse])
async def list_leagues(
    vendor: str | None = None,
    country: str | None = None,
    season: str | None = None,
    search: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    leagues = await service.list_leagues(db, vendor=vendor, country=country, season=season, search=search)
    return [LeagueResponse.model_validate(l) for l in leagues]


@router.post("/leagues", response_model=LeagueResponse)
async def upsert_league(
    body: LeagueCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    league = await service.upsert_league(
        db,
        vendor=body.vendor,
        league_id=body.league_id,
        name=body.name,
        country=body.country,
        season=body.season,
    )
    await db.commit()
    await db.refresh(league)
    return LeagueResponse.model_validate(league)


@router.get("/leagues/{league_id}", response_model=LeagueResponse)
async def get_league(
    league_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    league = await service.get_league_by_id(db, league_id)
    if league is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="League not found")
    return LeagueResponse.model_validate(league)
