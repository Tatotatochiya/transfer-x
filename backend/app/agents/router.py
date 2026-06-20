import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents import service
from app.agents.models import AgentCommission
from app.agents.schemas import (
    AgentCommissionsResponse,
    AgentCommissionResponse,
    AgentPipelineResponse,
    AgentProfileResponse,
    AgentUpdateRequest,
    CommissionStatusUpdate,
    DealSummary,
    InvitationResponse,
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


@router.get("/me/pipeline", response_model=AgentPipelineResponse)
async def get_pipeline(
    profile: AgentProfile = Depends(get_current_agent_profile),
    db: AsyncSession = Depends(get_db),
) -> AgentPipelineResponse:
    return await service.get_agent_pipeline(db, profile.id)


@router.get("/me/invitations", response_model=list[InvitationResponse])
async def list_invitations(
    profile: AgentProfile = Depends(get_current_agent_profile),
    db: AsyncSession = Depends(get_db),
) -> list[InvitationResponse]:
    invitations = await service.list_invitations(db, profile.id)
    return [
        InvitationResponse(
            id=inv.id,
            deal_id=inv.deal_id,
            status=inv.status,
            created_at=inv.created_at,
            deal=DealSummary(
                id=inv.deal.id,
                agreed_fee=inv.deal.agreed_fee,
                buyer_club_name=inv.deal.buyer_club.name if inv.deal.buyer_club else None,
                seller_club_name=inv.deal.seller_club.name if inv.deal.seller_club else None,
                player_name=inv.deal.player.name if inv.deal.player else None,
            ) if inv.deal else None,
        )
        for inv in invitations
    ]


# ── TRA-132: Commission endpoints ─────────────────────────────────────────────

@router.get("/me/commissions", response_model=AgentCommissionsResponse)
async def get_commissions(
    profile: AgentProfile = Depends(get_current_agent_profile),
    db: AsyncSession = Depends(get_db),
) -> AgentCommissionsResponse:
    data = await service.get_agent_commissions(db, profile.id)
    return AgentCommissionsResponse(
        summary=data["summary"],
        commissions=[AgentCommissionResponse.model_validate(c) for c in data["commissions"]],
    )


@router.patch("/me/commissions/{commission_id}/status", response_model=AgentCommissionResponse)
async def update_commission_status(
    commission_id: uuid.UUID,
    body: CommissionStatusUpdate,
    profile: AgentProfile = Depends(get_current_agent_profile),
    db: AsyncSession = Depends(get_db),
) -> AgentCommissionResponse:
    result = await db.execute(
        select(AgentCommission).where(
            AgentCommission.id == commission_id,
            AgentCommission.agent_id == profile.id,
        )
    )
    commission = result.scalar_one_or_none()
    if not commission:
        raise HTTPException(status_code=404, detail="Commission not found")
    try:
        commission = await service.update_commission_status(db, commission, new_status=body.status)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    await db.commit()
    return AgentCommissionResponse.model_validate(commission)
