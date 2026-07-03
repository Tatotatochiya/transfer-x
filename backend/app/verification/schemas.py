import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.verification.models import VerificationEntityType, VerificationStatus


class VerificationRequestCreate(BaseModel):
    evidence_ref: str | None = None
    notes: str | None = None


class VerificationReviewRequest(BaseModel):
    review_notes: str | None = None


class VerificationRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    entity_type: VerificationEntityType
    entity_id: uuid.UUID
    requested_by_user_id: uuid.UUID | None
    status: VerificationStatus
    evidence_ref: str | None
    notes: str | None
    reviewed_by_user_id: uuid.UUID | None
    reviewed_at: datetime | None
    review_notes: str | None
    created_at: datetime
    # Display helpers — set by the router, not the DB
    entity_name: str | None = None
    requested_by_email: str | None = None
