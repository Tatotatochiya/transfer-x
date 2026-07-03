"""TRA-89 — verification request workflow."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.verification.models import VerificationEntityType, VerificationRequest, VerificationStatus

_ACTIVE = {VerificationStatus.PENDING}


async def get_request_by_id(db: AsyncSession, request_id: uuid.UUID) -> VerificationRequest | None:
    result = await db.execute(select(VerificationRequest).where(VerificationRequest.id == request_id))
    return result.scalar_one_or_none()


async def get_pending_for_entity(
    db: AsyncSession, entity_type: VerificationEntityType, entity_id: uuid.UUID
) -> VerificationRequest | None:
    result = await db.execute(
        select(VerificationRequest).where(
            VerificationRequest.entity_type == entity_type,
            VerificationRequest.entity_id == entity_id,
            VerificationRequest.status == VerificationStatus.PENDING,
        )
    )
    return result.scalar_one_or_none()


async def list_requests_for_entity(
    db: AsyncSession, entity_type: VerificationEntityType, entity_id: uuid.UUID
) -> list[VerificationRequest]:
    result = await db.execute(
        select(VerificationRequest)
        .where(VerificationRequest.entity_type == entity_type, VerificationRequest.entity_id == entity_id)
        .order_by(VerificationRequest.created_at.desc())
    )
    return list(result.scalars())


async def list_requests(
    db: AsyncSession, status: VerificationStatus | None = None
) -> list[VerificationRequest]:
    """Admin queue — defaults to all requests, most recent first."""
    q = select(VerificationRequest)
    if status is not None:
        q = q.where(VerificationRequest.status == status)
    result = await db.execute(q.order_by(VerificationRequest.created_at.desc()))
    return list(result.scalars())


async def create_request(
    db: AsyncSession,
    *,
    entity_type: VerificationEntityType,
    entity_id: uuid.UUID,
    requested_by_user_id: uuid.UUID,
    evidence_ref: str | None,
    notes: str | None,
) -> VerificationRequest:
    existing = await get_pending_for_entity(db, entity_type, entity_id)
    if existing is not None:
        raise ValueError("A verification request is already pending for this entity")

    req = VerificationRequest(
        entity_type=entity_type,
        entity_id=entity_id,
        requested_by_user_id=requested_by_user_id,
        evidence_ref=evidence_ref,
        notes=notes,
    )
    db.add(req)
    await db.flush()
    return req


async def _set_entity_verified(
    db: AsyncSession, entity_type: VerificationEntityType, entity_id: uuid.UUID
) -> uuid.UUID | None:
    """Flip the entity's `verified` flag on and return its owning user_id (for notifications)."""
    if entity_type == VerificationEntityType.CLUB:
        from app.clubs.models import Club
        result = await db.execute(select(Club).where(Club.id == entity_id))
        club = result.scalar_one_or_none()
        if club is None:
            return None
        club.verified = True
        return club.user_id

    if entity_type == VerificationEntityType.AGENT:
        from app.auth.models import AgentProfile
        result = await db.execute(select(AgentProfile).where(AgentProfile.id == entity_id))
        agent = result.scalar_one_or_none()
        if agent is None:
            return None
        agent.verified = True
        return agent.user_id

    if entity_type == VerificationEntityType.PLAYER:
        from app.auth.models import PlayerProfile
        result = await db.execute(select(PlayerProfile).where(PlayerProfile.id == entity_id))
        pp = result.scalar_one_or_none()
        if pp is None:
            return None
        pp.verified = True
        return pp.user_id

    return None


async def approve_request(
    db: AsyncSession, request: VerificationRequest, *, reviewed_by_user_id: uuid.UUID
) -> VerificationRequest:
    if request.status != VerificationStatus.PENDING:
        raise ValueError(f"Cannot approve a request with status {request.status}")

    owner_user_id = await _set_entity_verified(db, request.entity_type, request.entity_id)

    request.status = VerificationStatus.APPROVED
    request.reviewed_by_user_id = reviewed_by_user_id
    request.reviewed_at = datetime.now(timezone.utc)
    await db.flush()

    if owner_user_id is not None:
        from app.notifications import service as notif_service
        from app.notifications.models import NotificationType
        await notif_service.create_notification(
            db,
            recipient_user_id=owner_user_id,
            type=NotificationType.VERIFICATION_APPROVED,
            message="Your verification request has been approved",
            link="/account",
        )

    return request


async def reject_request(
    db: AsyncSession,
    request: VerificationRequest,
    *,
    reviewed_by_user_id: uuid.UUID,
    review_notes: str | None,
) -> VerificationRequest:
    if request.status != VerificationStatus.PENDING:
        raise ValueError(f"Cannot reject a request with status {request.status}")

    request.status = VerificationStatus.REJECTED
    request.reviewed_by_user_id = reviewed_by_user_id
    request.reviewed_at = datetime.now(timezone.utc)
    request.review_notes = review_notes
    await db.flush()

    if request.requested_by_user_id is not None:
        from app.notifications import service as notif_service
        from app.notifications.models import NotificationType
        await notif_service.create_notification(
            db,
            recipient_user_id=request.requested_by_user_id,
            type=NotificationType.VERIFICATION_REJECTED,
            message="Your verification request was not approved" + (f": {review_notes}" if review_notes else ""),
            link="/account",
        )

    return request
