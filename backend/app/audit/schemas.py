"""TRA-62: Audit event response schemas."""
import uuid
from datetime import datetime

from pydantic import BaseModel


class AuditEventResponse(BaseModel):
    id: uuid.UUID
    actor_user_id: uuid.UUID | None
    actor_label: str | None = None
    entity_type: str
    entity_id: uuid.UUID
    action: str
    description: str | None
    payload_json: dict | None
    created_at: datetime

    class Config:
        from_attributes = True
