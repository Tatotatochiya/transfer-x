import uuid
from datetime import date, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.clubs import service as clubs_service
from app.clubs.schemas import (
    ClubPublicResponse,
    ClubResponse,
    ClubUpdateRequest,
    PlayerSearchViewCreateRequest,
    PlayerSearchViewResponse,
    PlayerSearchViewUpdateRequest,
)
from app.common.schemas import Paginated
from app.database import get_db
from app.deps import get_optional_user
from app.players import service as players_service
from app.players.schemas import ActiveDealStub, ContractResponse, PlayerDetailResponse
from app.world import service as world_service

router = APIRouter(tags=["clubs"])


@router.get("/me", response_model=ClubResponse)
async def get_my_club(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ClubResponse:
    club, my_role = await clubs_service.get_club_and_role_for_user(db, current_user.id)
    if club is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Club not found")
    return ClubResponse.model_validate(club).model_copy(update={"my_role": my_role})


@router.patch("/me", response_model=ClubResponse)
async def update_my_club(
    body: ClubUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ClubResponse:
    club, my_role = await clubs_service.get_club_and_role_for_user(db, current_user.id)
    if club is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Club not found")
    if my_role != "OWNER":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the club owner can edit club details")
    await clubs_service.update_club(db, club, **body.model_dump(exclude_none=True))
    await db.commit()
    await db.refresh(club)
    return ClubResponse.model_validate(club).model_copy(update={"my_role": my_role})


@router.get("", response_model=Paginated[ClubPublicResponse])
async def list_clubs(
    search: str | None = Query(None),
    country: str | None = Query(None),
    league_name: str | None = Query(None),
    sort_by: str = Query("name"),
    sort_dir: str = Query("asc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> Paginated[ClubPublicResponse]:
    clubs, total = await clubs_service.list_clubs(
        db,
        search=search,
        page=page,
        page_size=page_size,
        country=country,
        league_name=league_name,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    return Paginated(
        items=[ClubPublicResponse.model_validate(c) for c in clubs],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{club_id}", response_model=ClubPublicResponse)
async def get_club(club_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> ClubPublicResponse:
    club = await clubs_service.get_club_by_id(db, club_id)
    if club is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Club not found")
    return ClubPublicResponse.model_validate(club)


class _PlayerFlagsBody(BaseModel):
    open_to_offers: bool | None = None
    club_valuation: Decimal | None = None  # club's internal valuation; None clears it


@router.patch("/me/players/{player_id}", response_model=PlayerDetailResponse)
async def update_my_club_player(
    player_id: uuid.UUID,
    body: _PlayerFlagsBody,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PlayerDetailResponse:
    """Update player flags or internal valuation for a player in the current user's club."""
    club, _ = await clubs_service.get_club_and_role_for_user(db, current_user.id)
    if club is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No club profile")

    player = await players_service.get_player_by_id(db, player_id)
    if player is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Player not found")

    # Allow if player was created by this user, has an active contract with this club,
    # or is currently assigned to this club (e.g. admin-imported without a contract row)
    active_contract = next(
        (c for c in player.contracts if c.is_active and str(c.club_id) == str(club.id)),
        None,
    )
    in_squad = player.current_club_id is not None and str(player.current_club_id) == str(club.id)
    if player.created_by_user_id != current_user.id and active_contract is None and not in_squad:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Player not in your squad")

    # Block open_to_offers changes while a deal is in progress for this player
    if body.open_to_offers is not None:
        from app.deals import service as deals_service
        active_deal = await deals_service.get_active_deal_for_player(db, player_id)
        if active_deal and active_deal.status == "IN_PROGRESS":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot change offer availability while a transfer deal is in progress for this player.",
            )

    # Player-level flags
    player_updates = body.model_dump(exclude_none=True, exclude={"club_valuation"})
    if player_updates:
        await players_service.update_player(db, player, **player_updates)

    # Contract-level valuation (use exclude_unset so explicit null clears the field)
    if "club_valuation" in body.model_fields_set:
        if active_contract is not None:
            active_contract.club_valuation = body.club_valuation
        elif in_squad:
            # Player in squad with no formal contract row — cannot store valuation
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Player has no active contract row; valuation cannot be stored",
            )

    await db.commit()
    await db.refresh(player)

    data = PlayerDetailResponse.model_validate(player)
    if active_contract:
        await db.refresh(active_contract)
        data.active_contract = ContractResponse.model_validate(active_contract)
    return data


@router.post("/from-world-team/{world_team_id}", response_model=ClubResponse, status_code=status.HTTP_201_CREATED)
async def claim_world_team_as_club(
    world_team_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ClubResponse:
    """Create a marketplace Club pre-populated from a WorldTeam record.

    Fails with 409 if the user already has a club, or 404 if the world team doesn't exist.
    """
    existing, _ = await clubs_service.get_club_and_role_for_user(db, current_user.id)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You already have a club. Transfer or dissolve it first.",
        )

    team = await world_service.get_world_team_by_id(db, world_team_id)
    if team is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="World team not found")

    club = await clubs_service.create_club(
        db,
        user_id=current_user.id,
        name=team.name,
        role=clubs_service.ClubRole.BOTH,
    )
    # Carry over world-team metadata
    club.country = team.country
    club.league_name = team.league_name
    club.crest_url = team.crest_url

    await clubs_service.create_club_finance(db, club.id)
    await db.commit()
    await db.refresh(club)
    return ClubResponse.model_validate(club).model_copy(update={"my_role": "OWNER"})


# ── Player search views ───────────────────────────────────────────────────────

@router.get("/me/search-views", response_model=list[PlayerSearchViewResponse])
async def list_search_views(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[PlayerSearchViewResponse]:
    club, _ = await clubs_service.get_club_and_role_for_user(db, current_user.id)
    if club is None:
        return []
    views = await clubs_service.list_search_views(db, club.id)
    return [PlayerSearchViewResponse.model_validate(v) for v in views]


@router.post("/me/search-views", response_model=PlayerSearchViewResponse, status_code=status.HTTP_201_CREATED)
async def create_search_view(
    body: PlayerSearchViewCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PlayerSearchViewResponse:
    club, _ = await clubs_service.get_club_and_role_for_user(db, current_user.id)
    if club is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No club profile")
    view = await clubs_service.create_search_view(
        db, club_id=club.id, name=body.name, filters=body.filters, is_default=body.is_default
    )
    await db.commit()
    await db.refresh(view)
    return PlayerSearchViewResponse.model_validate(view)


@router.patch("/me/search-views/{view_id}", response_model=PlayerSearchViewResponse)
async def update_search_view(
    view_id: uuid.UUID,
    body: PlayerSearchViewUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PlayerSearchViewResponse:
    club, _ = await clubs_service.get_club_and_role_for_user(db, current_user.id)
    if club is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No club profile")
    view = await clubs_service.get_search_view(db, view_id, club.id)
    if view is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="View not found")
    view = await clubs_service.update_search_view(
        db, view, name=body.name, filters=body.filters, is_default=body.is_default
    )
    await db.commit()
    await db.refresh(view)
    return PlayerSearchViewResponse.model_validate(view)


@router.delete("/me/search-views/{view_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_search_view(
    view_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    club, _ = await clubs_service.get_club_and_role_for_user(db, current_user.id)
    if club is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No club profile")
    view = await clubs_service.get_search_view(db, view_id, club.id)
    if view is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="View not found")
    await clubs_service.delete_search_view(db, view)
    await db.commit()


@router.get("/{club_id}/players", response_model=Paginated[PlayerDetailResponse])
async def get_club_squad(
    club_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    current_user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
) -> Paginated[PlayerDetailResponse]:
    club = await clubs_service.get_club_by_id(db, club_id)
    if club is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Club not found")

    from app.deals import service as deals_service

    players, total = await players_service.list_club_squad(
        db,
        club_id=club_id,
        is_authenticated=current_user is not None,
        page=page,
        page_size=page_size,
    )

    player_ids = [p.id for p in players]
    deal_map = await deals_service.get_active_deals_for_players(db, player_ids)

    items = []
    for player in players:
        data = PlayerDetailResponse.model_validate(player)
        if current_user is not None:
            active = next((c for c in player.contracts if c.is_active), None)
            if active:
                data.active_contract = ContractResponse.model_validate(active)
        deal = deal_map.get(uuid.UUID(str(player.id)))
        if deal:
            data.active_deal = ActiveDealStub.model_validate(deal)
        items.append(data)

    return Paginated(items=items, total=total, page=page, page_size=page_size)


# ── Expiring contracts ────────────────────────────────────────────────────────

class ExpiringContractItem(BaseModel):
    player_id: str
    player_name: str
    position: str | None
    end_date: date
    days_remaining: int


@router.get("/me/expiring-contracts", response_model=list[ExpiringContractItem])
async def get_expiring_contracts(
    within_days: int = Query(default=180, ge=30, le=365),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Squad players whose active contracts expire within `within_days` days."""
    from app.players.models import Contract, Player

    club = await clubs_service.get_club_by_user_id(db, current_user.id)
    if club is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No club profile")

    cutoff = date.today() + timedelta(days=within_days)

    result = await db.execute(
        select(Player, Contract)
        .join(Contract, Contract.player_id == Player.id)
        .where(
            Player.current_club_id == club.id,
            Contract.is_active == True,  # noqa: E712
            Contract.end_date.is_not(None),
            Contract.end_date <= cutoff,
        )
        .order_by(Contract.end_date.asc())
    )
    rows = result.all()
    today = date.today()
    return [
        ExpiringContractItem(
            player_id=str(player.id),
            player_name=player.name,
            position=player.position,
            end_date=contract.end_date,
            days_remaining=(contract.end_date - today).days,
        )
        for player, contract in rows
    ]
