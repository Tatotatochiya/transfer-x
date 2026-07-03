import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DealTermsVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    deal_id: uuid.UUID
    version_number: int
    terms_snapshot: dict
    changed_by_user_id: uuid.UUID | None
    changed_by_label: str | None = None
    created_at: datetime


class TermsDiffField(BaseModel):
    field: str
    old_value: object | None
    new_value: object | None


class TermsDiffResponse(BaseModel):
    from_version: int | None
    to_version: int | None
    changes: list[TermsDiffField]


class DealCommentCreateRequest(BaseModel):
    body: str
    parent_id: uuid.UUID | None = None
    mentioned_user_ids: list[uuid.UUID] = []


class DealCommentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    deal_id: uuid.UUID
    parent_id: uuid.UUID | None
    author_user_id: uuid.UUID | None
    author_label: str | None = None
    body: str
    mentioned_user_ids: list[str]
    created_at: datetime


class DealParticipant(BaseModel):
    user_id: uuid.UUID
    label: str


class DealAttachmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    deal_id: uuid.UUID
    uploaded_by_user_id: uuid.UUID | None
    uploaded_by_label: str | None = None
    filename: str
    content_type: str
    size_bytes: int
    created_at: datetime
