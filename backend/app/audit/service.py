"""TRA-62: Audit event helpers — append-only, no update/delete paths."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.models import AuditEvent


async def emit(
    db: AsyncSession,
    *,
    entity_type: str,
    entity_id: uuid.UUID,
    action: str,
    actor_user_id: uuid.UUID | None = None,
    payload: dict | None = None,
    description: str | None = None,
) -> AuditEvent:
    """Append an immutable audit event. Call before db.commit()."""
    event = AuditEvent(
        id=uuid.uuid4(),
        actor_user_id=actor_user_id,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        payload_json=payload,
        description=description,
        created_at=datetime.now(timezone.utc),
    )
    db.add(event)
    await db.flush()
    return event


async def get_events_for_entity(
    db: AsyncSession,
    entity_type: str,
    entity_id: uuid.UUID,
) -> list[AuditEvent]:
    result = await db.execute(
        select(AuditEvent)
        .where(AuditEvent.entity_type == entity_type, AuditEvent.entity_id == entity_id)
        .order_by(AuditEvent.created_at)
    )
    return list(result.scalars().all())
