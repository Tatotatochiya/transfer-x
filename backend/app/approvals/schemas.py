import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.approvals.models import ApprovalActionType, ApprovalStatus


class PendingApprovalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    club_id: uuid.UUID
    action_type: ApprovalActionType
    amount: Decimal
    requested_by_user_id: uuid.UUID
    requested_by_email: str | None = None  # set by router
    status: ApprovalStatus
    decided_by_user_id: uuid.UUID | None
    decided_at: datetime | None
    failure_reason: str | None
    created_at: datetime
    expires_at: datetime
    summary: str | None


class ApprovalRejectRequest(BaseModel):
    reason: str | None = None


class ApprovalPolicyResponse(BaseModel):
    approval_threshold: Decimal | None


class ApprovalPolicyUpdateRequest(BaseModel):
    # Explicit null disables the feature (D7 default).
    approval_threshold: Decimal | None = None


class PendingApprovalCaptured(BaseModel):
    """The 202 body returned when a money action is captured instead of executed."""
    status: str = "PENDING_APPROVAL"
    approval_id: uuid.UUID
