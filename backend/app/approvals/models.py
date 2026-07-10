"""Spending-authority approvals (club-team-roles spec, Phase 5 / D7).

A pending approval is an *intent*, not a hold: nothing is reserved when it is
captured, and everything (budget, transfer window, auction state) is
re-validated fresh when an approver executes it.
"""
import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import JSON, DateTime, ForeignKey, Numeric, String, Text, Uuid, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ApprovalActionType(str, enum.Enum):
    PLACE_BID = "PLACE_BID"
    CREATE_OFFER = "CREATE_OFFER"
    ACCEPT_OFFER = "ACCEPT_OFFER"
    ACCEPT_BID = "ACCEPT_BID"


class ApprovalStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED_EXECUTED = "APPROVED_EXECUTED"
    APPROVED_FAILED = "APPROVED_FAILED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


class PendingApproval(Base):
    __tablename__ = "pending_approvals"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    club_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    action_type: Mapped[ApprovalActionType] = mapped_column(
        SAEnum(ApprovalActionType, name="approvalactiontype"), nullable=False
    )
    # The validated request payload, replayed at execution time. JSONB on
    # Postgres, plain JSON elsewhere so the SQLite test suite stays collectible.
    payload_json: Mapped[dict] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    requested_by_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[ApprovalStatus] = mapped_column(
        SAEnum(ApprovalStatus, name="approvalstatus"),
        nullable=False,
        default=ApprovalStatus.PENDING,
        index=True,
    )
    decided_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # Human-readable context captured at request time (player/sale names) so the
    # queue renders without re-resolving entities that may since have changed.
    summary: Mapped[str | None] = mapped_column(String(500), nullable=True)
