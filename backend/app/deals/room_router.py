"""TRA-81 — deal room: versioned terms, threaded comments, attachments."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.database import get_db
from app.deals import service as deals_service
from app.deals import room_service as service
from app.deals.room_schemas import (
    DealAttachmentResponse,
    DealCommentCreateRequest,
    DealCommentResponse,
    DealParticipant,
    DealTermsVersionResponse,
    TermsDiffResponse,
)
from app.clubs.capabilities import Capability, ensure_capability_if_club_member
from app.deps import get_current_user

router = APIRouter(tags=["deal-room"])


async def _get_deal_or_404(db: AsyncSession, deal_id: uuid.UUID):
    deal = await deals_service.get_deal_by_id(db, deal_id)
    if deal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deal not found")
    return deal


async def _require_participant(db: AsyncSession, deal, current_user: User) -> None:
    if not await service.is_deal_participant(db, deal, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a party to this deal")


# ── Versioned terms ────────────────────────────────────────────────────────────


@router.get("/deals/{deal_id}/versions", response_model=list[DealTermsVersionResponse])
async def list_versions(
    deal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    deal = await _get_deal_or_404(db, deal_id)
    await _require_participant(db, deal, current_user)

    versions = await service.list_terms_versions(db, deal_id)
    responses = []
    for v in versions:
        resp = DealTermsVersionResponse.model_validate(v)
        resp.changed_by_label = await service.label_for_user(db, v.changed_by_user_id)
        responses.append(resp)
    return responses


@router.get("/deals/{deal_id}/versions/diff", response_model=TermsDiffResponse)
async def diff_versions(
    deal_id: uuid.UUID,
    from_version: int | None = None,
    to_version: int | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    deal = await _get_deal_or_404(db, deal_id)
    await _require_participant(db, deal, current_user)

    from_v, to_v, changes = await service.diff_versions(db, deal_id, from_version, to_version)
    return TermsDiffResponse(from_version=from_v, to_version=to_v, changes=changes)


# ── Comments ───────────────────────────────────────────────────────────────────


@router.get("/deals/{deal_id}/participants", response_model=list[DealParticipant])
async def list_participants(
    deal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    deal = await _get_deal_or_404(db, deal_id)
    await _require_participant(db, deal, current_user)
    return await service.get_deal_participants(db, deal)


@router.get("/deals/{deal_id}/comments", response_model=list[DealCommentResponse])
async def list_comments(
    deal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    deal = await _get_deal_or_404(db, deal_id)
    await _require_participant(db, deal, current_user)

    comments = await service.list_comments(db, deal_id)
    responses = []
    for c in comments:
        resp = DealCommentResponse.model_validate(c)
        resp.author_label = await service.label_for_user(db, c.author_user_id)
        responses.append(resp)
    return responses


@router.post("/deals/{deal_id}/comments", response_model=DealCommentResponse, status_code=status.HTTP_201_CREATED)
async def post_comment(
    deal_id: uuid.UUID,
    body: DealCommentCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    deal = await _get_deal_or_404(db, deal_id)
    await _require_participant(db, deal, current_user)
    # TRA-151: the room is shared with agents/players (participant-gated above);
    # club members additionally need DEAL_WRITE — READONLY/SCOUT view only.
    await ensure_capability_if_club_member(db, current_user, Capability.DEAL_WRITE)

    if not body.body.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Comment cannot be empty")

    parent = None
    if body.parent_id is not None:
        parent = await service.get_comment(db, body.parent_id)
        if parent is None or parent.deal_id != deal_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parent comment not found")

    comment = await service.create_comment(
        db, deal_id,
        author_user_id=current_user.id,
        body=body.body.strip(),
        parent_id=body.parent_id,
        mentioned_user_ids=body.mentioned_user_ids,
    )

    # Notify mentioned users + the parent comment's author (if replying), excluding the author themself.
    from app.notifications import service as notif_service
    from app.notifications.models import NotificationType
    to_notify = set(body.mentioned_user_ids)
    if parent is not None and parent.author_user_id is not None:
        to_notify.add(parent.author_user_id)
    to_notify.discard(current_user.id)
    for recipient_id in to_notify:
        await notif_service.create_notification(
            db,
            recipient_user_id=recipient_id,
            type=NotificationType.NEGOTIATION_MESSAGE,
            message="New comment in a deal you're part of",
            link=f"/deals/{deal_id}",
            related_player_id=deal.player_id,
        )

    await db.commit()
    await db.refresh(comment)
    resp = DealCommentResponse.model_validate(comment)
    resp.author_label = await service.label_for_user(db, comment.author_user_id)
    return resp


# ── Attachments ────────────────────────────────────────────────────────────────


@router.get("/deals/{deal_id}/attachments", response_model=list[DealAttachmentResponse])
async def list_attachments(
    deal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    deal = await _get_deal_or_404(db, deal_id)
    await _require_participant(db, deal, current_user)

    attachments = await service.list_attachments(db, deal_id)
    responses = []
    for a in attachments:
        resp = DealAttachmentResponse.model_validate(a)
        resp.uploaded_by_label = await service.label_for_user(db, a.uploaded_by_user_id)
        responses.append(resp)
    return responses


@router.post(
    "/deals/{deal_id}/attachments",
    response_model=DealAttachmentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_attachment(
    deal_id: uuid.UUID,
    file: UploadFile,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    deal = await _get_deal_or_404(db, deal_id)
    await _require_participant(db, deal, current_user)
    # TRA-151: as with comments — club members need DEAL_WRITE to upload.
    await ensure_capability_if_club_member(db, current_user, Capability.DEAL_WRITE)

    content = await file.read()
    try:
        safe_filename = service.validate_attachment(file.filename or "attachment", len(content))
    except service.AttachmentValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    storage_path = service.save_attachment_bytes(deal_id, safe_filename, content)
    attachment = await service.create_attachment(
        db, deal_id,
        uploaded_by_user_id=current_user.id,
        filename=safe_filename,
        content_type=file.content_type or "application/octet-stream",
        size_bytes=len(content),
        storage_path=storage_path,
    )
    await db.commit()
    await db.refresh(attachment)
    resp = DealAttachmentResponse.model_validate(attachment)
    resp.uploaded_by_label = await service.label_for_user(db, attachment.uploaded_by_user_id)
    return resp


@router.get("/deals/{deal_id}/attachments/{attachment_id}/download")
async def download_attachment(
    deal_id: uuid.UUID,
    attachment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    deal = await _get_deal_or_404(db, deal_id)
    await _require_participant(db, deal, current_user)

    attachment = await service.get_attachment(db, deal_id, attachment_id)
    if attachment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found")

    content = service.read_attachment_bytes(attachment.storage_path)
    return Response(
        content=content,
        media_type=attachment.content_type,
        headers={"Content-Disposition": f'attachment; filename="{attachment.filename}"'},
    )
