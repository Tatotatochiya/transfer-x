import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import AgentProfile
from app.database import get_db
from app.deps import get_current_agent_profile
from app.mandates import service
from app.mandates.schemas import CreateMandateRequest, MandateResponse

router = APIRouter(tags=["mandates"])


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
