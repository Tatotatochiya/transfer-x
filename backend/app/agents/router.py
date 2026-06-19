from fastapi import APIRouter, Depends, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents import service
from app.agents.schemas import (
    AgentProfileResponse,
    AgentUpdateRequest,
    RepresentedPlayerItem,
    RosterImportRequest,
    RosterImportResult,
    RosterPreviewResponse,
)
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
            client_status=mandate.client_status,
        )
        for mandate, player in rows
    ]


@router.post("/me/roster/preview", response_model=RosterPreviewResponse)
async def preview_roster_import(
    file: UploadFile,
    profile: AgentProfile = Depends(get_current_agent_profile),
    db: AsyncSession = Depends(get_db),
) -> RosterPreviewResponse:
    content = await file.read()
    return await service.parse_csv_roster(db, content)


@router.post("/me/roster/import", response_model=RosterImportResult)
async def import_roster(
    body: RosterImportRequest,
    profile: AgentProfile = Depends(get_current_agent_profile),
    db: AsyncSession = Depends(get_db),
) -> RosterImportResult:
    result = await service.import_roster(db, profile.id, body)
    await db.commit()
    return result
