from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents import service
from app.agents.schemas import AgentProfileResponse, AgentUpdateRequest, RepresentedPlayerItem
from app.auth.models import AgentProfile
from app.database import get_db
from app.deps import get_current_agent_profile

router = APIRouter(tags=["agents"])


@router.get("/me", response_model=AgentProfileResponse)
async def get_agent_profile(
    profile: AgentProfile = Depends(get_current_agent_profile),
) -> AgentProfileResponse:
    return AgentProfileResponse.model_validate(profile)


@router.patch("/me", response_model=AgentProfileResponse)
async def update_agent_profile(
    body: AgentUpdateRequest,
    profile: AgentProfile = Depends(get_current_agent_profile),
    db: AsyncSession = Depends(get_db),
) -> AgentProfileResponse:
    updates = body.model_dump(exclude_none=True)
    if updates:
        await service.update_profile(db, profile, **updates)
        await db.commit()
    return AgentProfileResponse.model_validate(profile)


@router.get("/me/players", response_model=list[RepresentedPlayerItem])
async def list_represented_players(
    profile: AgentProfile = Depends(get_current_agent_profile),
    db: AsyncSession = Depends(get_db),
) -> list[RepresentedPlayerItem]:
    rows = await service.list_represented_players(db, profile.id)
    return [
        RepresentedPlayerItem(
            mandate_id=mandate.id,
            player_id=player.id,
            player_name=player.name,
            player_position=str(player.position) if player.position else None,
            exclusive=mandate.exclusive,
            start_date=mandate.start_date,
            end_date=mandate.end_date,
            status=mandate.status,
        )
        for mandate, player in rows
    ]
