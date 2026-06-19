import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import AgentProfile
from app.database import get_db
from app.deps import get_current_agent_profile
from app.mandates import service
from app.mandates.schemas import (
    CreateMandateRequest,
    MandateDetailResponse,
    MandateResponse,
    UpdateMandateRequest,
)

router = APIRouter(tags=["mandates"])


def _build_detail(mandate, player, contract) -> MandateDetailResponse:
    return MandateDetailResponse(
        id=mandate.id,
        agent_id=mandate.agent_id,
        player_id=mandate.player_id,
        start_date=mandate.start_date,
        end_date=mandate.end_date,
        exclusive=mandate.exclusive,
        territory=mandate.territory,
        status=mandate.status,
        created_at=mandate.created_at,
        client_status=mandate.client_status,
        agent_notes=mandate.agent_notes,
        preferred_destinations=mandate.preferred_destinations,
        asking_price=mandate.asking_price,
        asking_wage=mandate.asking_wage,
        player_name=player.name,
        player_position=str(player.position) if player.position else None,
        player_nationality=player.nationality,
        player_age=player.age,
        player_club_name=player.current_club.name if player.current_club else player.team_name,
        contract_expiry=contract.end_date if contract else None,
    )


@router.post("/", response_model=MandateResponse, status_code=status.HTTP_201_CREATED)
async def create_mandate(
    body: CreateMandateRequest,
    agent_profile: AgentProfile = Depends(get_current_agent_profile),
    db: AsyncSession = Depends(get_db),
) -> MandateResponse:
    try:
        mandate = await service.create_mandate(
            db,
            agent_profile_id=agent_profile.id,
            player_id=body.player_id,
            exclusive=body.exclusive,
            start_date=body.start_date,
            end_date=body.end_date,
            territory=body.territory,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    await db.commit()
    return MandateResponse.model_validate(mandate)


@router.get("/{mandate_id}", response_model=MandateDetailResponse)
async def get_mandate_detail(
    mandate_id: uuid.UUID,
    agent_profile: AgentProfile = Depends(get_current_agent_profile),
    db: AsyncSession = Depends(get_db),
) -> MandateDetailResponse:
    try:
        mandate, player, contract = await service.get_mandate_detail(
            db, mandate_id=mandate_id, agent_profile_id=agent_profile.id
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return _build_detail(mandate, player, contract)


@router.patch("/{mandate_id}", response_model=MandateDetailResponse)
async def update_mandate(
    mandate_id: uuid.UUID,
    body: UpdateMandateRequest,
    agent_profile: AgentProfile = Depends(get_current_agent_profile),
    db: AsyncSession = Depends(get_db),
) -> MandateDetailResponse:
    updates = body.model_dump(exclude_unset=True)
    try:
        await service.patch_mandate(
            db, mandate_id=mandate_id, agent_profile_id=agent_profile.id, updates=updates
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    await db.commit()
    mandate, player, contract = await service.get_mandate_detail(
        db, mandate_id=mandate_id, agent_profile_id=agent_profile.id
    )
    return _build_detail(mandate, player, contract)


@router.post("/{mandate_id}/revoke", response_model=MandateResponse)
async def revoke_mandate(
    mandate_id: uuid.UUID,
    agent_profile: AgentProfile = Depends(get_current_agent_profile),
    db: AsyncSession = Depends(get_db),
) -> MandateResponse:
    try:
        mandate = await service.revoke_mandate(
            db, mandate_id=mandate_id, agent_profile_id=agent_profile.id
        )
    except ValueError as exc:
        detail = str(exc)
        if "not found" in detail.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)
    await db.commit()
    return MandateResponse.model_validate(mandate)
