"""TRA-62: Audit log endpoints — deal history + CSV export."""
import csv
import io
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.schemas import AuditEventResponse
from app.audit.service import get_events_for_entity
from app.auth.models import User
from app.database import get_db
from app.deps import get_current_user

router = APIRouter(tags=["audit"])


async def _get_deal_and_authorize(db: AsyncSession, deal_id: uuid.UUID, current_user: User):
    """TRA-141: only deal participants (or staff) may read a deal's audit log."""
    from app.deals import room_service
    from app.deals import service as deals_service

    deal = await deals_service.get_deal_by_id(db, deal_id)
    if deal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deal not found")
    if not await room_service.is_deal_participant(db, deal, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a party to this deal")
    return deal


@router.get("/deals/{deal_id}/audit-log", response_model=list[AuditEventResponse])
async def deal_audit_log(
    deal_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[AuditEventResponse]:
    from app.deals import room_service

    await _get_deal_and_authorize(db, deal_id, current_user)
    events = await get_events_for_entity(db, "DEAL", deal_id)
    responses = []
    for e in events:
        resp = AuditEventResponse.model_validate(e)
        resp.actor_label = await room_service.label_for_user(db, e.actor_user_id)
        responses.append(resp)
    return responses


@router.get("/deals/{deal_id}/audit-log/export.csv")
async def deal_audit_log_csv(
    deal_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    from app.deals import room_service

    await _get_deal_and_authorize(db, deal_id, current_user)
    events = await get_events_for_entity(db, "DEAL", deal_id)

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["timestamp", "action", "actor", "description", "payload"])
    for e in events:
        actor_label = await room_service.label_for_user(db, e.actor_user_id)
        writer.writerow([
            e.created_at.isoformat(),
            e.action,
            actor_label or "",
            e.description or "",
            str(e.payload_json) if e.payload_json else "",
        ])

    buf.seek(0)
    filename = f"deal_{deal_id}_audit.csv"
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
