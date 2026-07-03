import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User, UserType
from app.database import get_db
from app.deps import get_current_superuser, get_current_user
from app.verification import service
from app.verification.models import VerificationEntityType, VerificationRequest, VerificationStatus
from app.verification.schemas import (
    VerificationRequestCreate,
    VerificationRequestResponse,
    VerificationReviewRequest,
)

router = APIRouter(prefix="/verification", tags=["verification"])


async def _resolve_actor_entity(db: AsyncSession, user: User) -> tuple[VerificationEntityType, uuid.UUID, str]:
    """Map the calling user to the entity_type/entity_id/display_name they can request verification for."""
    if user.user_type == UserType.CLUB:
        from app.clubs import service as clubs_service
        club = await clubs_service.get_club_by_user_id(db, user.id)
        if club is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No club profile")
        return VerificationEntityType.CLUB, club.id, club.name

    if user.user_type == UserType.AGENT:
        from app.auth.models import AgentProfile
        result = await db.execute(select(AgentProfile).where(AgentProfile.user_id == user.id))
        agent = result.scalar_one_or_none()
        if agent is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No agent profile")
        return VerificationEntityType.AGENT, agent.id, agent.display_name

    if user.user_type == UserType.PLAYER:
        from app.auth.models import PlayerProfile
        from app.players.models import Player
        result = await db.execute(select(PlayerProfile).where(PlayerProfile.user_id == user.id))
        pp = result.scalar_one_or_none()
        if pp is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No player profile")
        player_result = await db.execute(select(Player).where(Player.id == pp.player_id))
        player = player_result.scalar_one_or_none()
        return VerificationEntityType.PLAYER, pp.id, (player.name if player else "Player")

    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This account type cannot request verification")


async def _entity_display_name(
    db: AsyncSession, entity_type: VerificationEntityType, entity_id: uuid.UUID
) -> str | None:
    if entity_type == VerificationEntityType.CLUB:
        from app.clubs.models import Club
        result = await db.execute(select(Club.name).where(Club.id == entity_id))
        return result.scalar_one_or_none()

    if entity_type == VerificationEntityType.AGENT:
        from app.auth.models import AgentProfile
        result = await db.execute(select(AgentProfile.display_name).where(AgentProfile.id == entity_id))
        return result.scalar_one_or_none()

    if entity_type == VerificationEntityType.PLAYER:
        from app.auth.models import PlayerProfile
        from app.players.models import Player
        result = await db.execute(
            select(Player.name).join(PlayerProfile, PlayerProfile.player_id == Player.id)
            .where(PlayerProfile.id == entity_id)
        )
        return result.scalar_one_or_none()

    return None


async def _to_response(db: AsyncSession, req: VerificationRequest) -> VerificationRequestResponse:
    resp = VerificationRequestResponse.model_validate(req)
    if req.requested_by_user_id is not None:
        result = await db.execute(select(User.email).where(User.id == req.requested_by_user_id))
        resp.requested_by_email = result.scalar_one_or_none()
    resp.entity_name = await _entity_display_name(db, req.entity_type, req.entity_id)
    return resp


@router.post("/requests", response_model=VerificationRequestResponse, status_code=status.HTTP_201_CREATED)
async def request_verification(
    body: VerificationRequestCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    entity_type, entity_id, _ = await _resolve_actor_entity(db, current_user)
    try:
        req = await service.create_request(
            db,
            entity_type=entity_type,
            entity_id=entity_id,
            requested_by_user_id=current_user.id,
            evidence_ref=body.evidence_ref,
            notes=body.notes,
        )
        await db.commit()
        await db.refresh(req)
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return await _to_response(db, req)


@router.get("/requests/mine", response_model=list[VerificationRequestResponse])
async def list_my_requests(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    entity_type, entity_id, _ = await _resolve_actor_entity(db, current_user)
    requests = await service.list_requests_for_entity(db, entity_type, entity_id)
    return [await _to_response(db, r) for r in requests]


# ── Admin review queue ────────────────────────────────────────────────────────


@router.get("/requests", response_model=list[VerificationRequestResponse])
async def list_verification_requests(
    request_status: VerificationStatus | None = None,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_current_superuser),
):
    requests = await service.list_requests(db, status=request_status)
    return [await _to_response(db, r) for r in requests]


@router.post("/requests/{request_id}/approve", response_model=VerificationRequestResponse)
async def approve_verification_request(
    request_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_superuser),
):
    req = await service.get_request_by_id(db, request_id)
    if req is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    try:
        req = await service.approve_request(db, req, reviewed_by_user_id=admin.id)
        await db.commit()
        await db.refresh(req)
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return await _to_response(db, req)


@router.post("/requests/{request_id}/reject", response_model=VerificationRequestResponse)
async def reject_verification_request(
    request_id: uuid.UUID,
    body: VerificationReviewRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_superuser),
):
    req = await service.get_request_by_id(db, request_id)
    if req is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    try:
        req = await service.reject_request(
            db, req, reviewed_by_user_id=admin.id, review_notes=body.review_notes
        )
        await db.commit()
        await db.refresh(req)
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return await _to_response(db, req)
