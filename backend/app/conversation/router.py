import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.clubs import service as clubs_service
from app.conversation import service
from app.database import get_db

router = APIRouter(tags=["conversation"])

Audience = Literal["both_clubs", "deal_everyone", "our_club", "with_agent"]


class ConversationMessage(BaseModel):
    id: uuid.UUID
    source: Literal["enquiry", "offer", "deal", "agent"]
    audience: Audience
    audience_label: str
    author: str
    mine: bool
    body: str
    created_at: datetime
    context: str


class AudienceOption(BaseModel):
    key: Audience
    label: str


class ConversationResponse(BaseModel):
    messages: list[ConversationMessage]
    can_post_to: list[AudienceOption]


class ConversationPost(BaseModel):
    offer_id: uuid.UUID | None = None
    deal_id: uuid.UUID | None = None
    enquiry_id: uuid.UUID | None = None
    audience: Audience
    body: str = Field(min_length=1, max_length=4000)


async def _load(db, user, offer_id, deal_id, enquiry_id):
    club, _ = await clubs_service.get_club_and_role_for_user(db, user.id)
    if club is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No club profile")
    try:
        t = await service.resolve(db, club.id, offer_id=offer_id, deal_id=deal_id, enquiry_id=enquiry_id)
    except service.ConversationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
    return club, t


async def _response(db, t, user) -> ConversationResponse:
    return ConversationResponse(
        messages=[ConversationMessage(**m) for m in await service.messages(db, t, user)],
        can_post_to=[AudienceOption(key=k, label=service.AUDIENCE_LABEL[k]) for k in await service.post_options(db, t)],
    )


@router.get("/conversation", response_model=ConversationResponse)
async def get_conversation(
    offer_id: uuid.UUID | None = None,
    deal_id: uuid.UUID | None = None,
    enquiry_id: uuid.UUID | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConversationResponse:
    """Everything said about one transfer (enquiry, offers, deal and the agent
    thread) that this club can see, in order (product ADR 0008)."""
    _club, t = await _load(db, current_user, offer_id, deal_id, enquiry_id)
    return await _response(db, t, current_user)


@router.post("/conversation", response_model=ConversationResponse)
async def post_to_conversation(
    body: ConversationPost,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConversationResponse:
    club, t = await _load(db, current_user, body.offer_id, body.deal_id, body.enquiry_id)
    try:
        await service.post(db, t, current_user, club, audience=body.audience, body=body.body)
    except service.ConversationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
    _club, t = await _load(db, current_user, body.offer_id, body.deal_id, body.enquiry_id)
    return await _response(db, t, current_user)
