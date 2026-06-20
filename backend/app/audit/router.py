"""TRA-62: Audit log endpoints — deal history + CSV export."""
import csv
import io
import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.schemas import AuditEventResponse
from app.audit.service import get_events_for_entity
from app.auth.models import User
from app.database import get_db
from app.deps import get_current_user

router = APIRouter(tags=["audit"])


@router.get("/deals/{deal_id}/audit-log", response_model=list[AuditEventResponse])
async def deal_audit_log(
    deal_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[AuditEventResponse]:
    events = await get_events_for_entity(db, "DEAL", deal_id)
    return [AuditEventResponse.model_validate(e) for e in events]


@router.get("/deals/{deal_id}/audit-log/export.csv")
async def deal_audit_log_csv(
    deal_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    events = await get_events_for_entity(db, "DEAL", deal_id)

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["timestamp", "action", "actor_user_id", "description", "payload"])
    for e in events:
        writer.writerow([
            e.created_at.isoformat(),
            e.action,
            str(e.actor_user_id) if e.actor_user_id else "",
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
