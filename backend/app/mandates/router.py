import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import AgentProfile, PlayerProfile
from app.database import get_db
from app.deps import get_current_agent_profile
from app.mandates import alerts_service, service
from app.mandates.models import Mandate
from app.mandates.schemas import (
    ClientAlertResponse,
    CreateMandateRequest,
    MandateDetailResponse,
    MandateResponse,
    UpdateMandateRequest,
)
from app.notifications import service as notif_service
from app.notifications.models import NotificationType

router = APIRouter(tags=["mandates"])


async def _notify_player_of_mandate(db: AsyncSession, mandate, agent_profile: AgentProfile) -> None:
    result = await db.execute(select(PlayerProfile).where(PlayerProfile.player_id == mandate.player_id))
    player_profile = result.scalar_one_or_none()
    if player_profile is None:
        return  # Player has no login account — nothing to notify
    await notif_service.create_notification(
        db,
        recipient_user_id=player_profile.user_id,
        type=NotificationType.REPRESENTATION_STARTED,
        message=f"{agent_profile.display_name} ({agent_profile.agency_name}) is now representing you",
        link="/player/profile",
    )


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
        alert_contract_expiry_enabled=mandate.alert_contract_expiry_enabled,
        alert_contract_expiry_months=mandate.alert_contract_expiry_months,
        alert_valuation_change_enabled=mandate.alert_valuation_change_enabled,
        alert_valuation_change_pct=mandate.alert_valuation_change_pct,
        alert_club_interest_enabled=mandate.alert_club_interest_enabled,
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
        await _notify_player_of_mandate(db, mandate, agent_profile)
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


@router.get("/{mandate_id}/alerts", response_model=list[ClientAlertResponse])
async def list_mandate_alerts(
    mandate_id: uuid.UUID,
    agent_profile: AgentProfile = Depends(get_current_agent_profile),
    db: AsyncSession = Depends(get_db),
) -> list[ClientAlertResponse]:
    mandate = await db.get(Mandate, mandate_id)
    if mandate is None or mandate.agent_id != agent_profile.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mandate not found")
    alerts = await alerts_service.list_alerts_for_mandate(db, mandate_id)
    return [ClientAlertResponse.model_validate(a) for a in alerts]
