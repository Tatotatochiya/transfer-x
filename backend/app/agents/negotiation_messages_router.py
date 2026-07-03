"""TRA-136 — GET/POST /negotiations/{id}/messages."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents import negotiation_messages as service
from app.agents.models import NegotiationThread
from app.agents.schemas import NegotiationMessageCreateRequest, NegotiationMessageResponse
from app.auth.models import User
from app.database import get_db
from app.deps import get_current_user

router = APIRouter(prefix="/negotiations", tags=["negotiation-messages"])


async def _to_response(db: AsyncSession, msg) -> NegotiationMessageResponse:
    resp = NegotiationMessageResponse.model_validate(msg)
    if msg.sender_user_id is not None:
        result = await db.execute(select(User).where(User.id == msg.sender_user_id))
        sender = result.scalar_one_or_none()
        if sender is not None:
            resp.sender_label = await service.sender_label(db, sender)
    return resp


@router.get("/{negotiation_id}/messages", response_model=list[NegotiationMessageResponse])
async def list_negotiation_messages(
    negotiation_id: uuid.UUID,
    thread: NegotiationThread | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    loaded = await service.get_negotiation_with_deal(db, negotiation_id)
    if loaded is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Negotiation not found")
    negotiation, deal = loaded

    allowed = await service.resolve_allowed_threads(db, negotiation, deal, current_user)
    if not allowed:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a party to this negotiation")

    if thread is not None:
        if thread not in allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"No access to {thread.value}")
        threads = {thread}
    else:
        threads = allowed

    messages = await service.list_messages(db, negotiation_id, threads)
    return [await _to_response(db, m) for m in messages]


@router.post(
    "/{negotiation_id}/messages",
    response_model=NegotiationMessageResponse,
    status_code=status.HTTP_201_CREATED,
)
async def post_negotiation_message(
    negotiation_id: uuid.UUID,
    body: NegotiationMessageCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    loaded = await service.get_negotiation_with_deal(db, negotiation_id)
    if loaded is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Negotiation not found")
    negotiation, deal = loaded

    allowed = await service.resolve_allowed_threads(db, negotiation, deal, current_user)
    if body.thread not in allowed:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"No access to {body.thread.value}")

    if not body.body.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Message cannot be empty")

    msg = await service.create_message(
        db,
        negotiation_id=negotiation_id,
        thread=body.thread,
        sender_user_id=current_user.id,
        body=body.body.strip(),
    )
    await service.notify_counterparty(db, negotiation=negotiation, deal=deal, thread=body.thread, sender=current_user)
    await db.commit()
    await db.refresh(msg)
    return await _to_response(db, msg)
