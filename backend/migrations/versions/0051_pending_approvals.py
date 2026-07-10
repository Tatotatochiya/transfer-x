"""Phase 5 (club-team-roles spec): approval thresholds + pending approvals.

Revision ID: 0051
Revises: 0050
Create Date: 2026-07-10
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision: str = "0051"
down_revision: Union[str, None] = "0050"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'APPROVAL_REQUESTED'")
    op.execute("ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'APPROVAL_DECIDED'")

    op.add_column(
        "club_finances",
        sa.Column("approval_threshold", sa.Numeric(15, 2), nullable=True),
    )

    op.execute(
        "CREATE TYPE approvalactiontype AS ENUM "
        "('PLACE_BID', 'CREATE_OFFER', 'ACCEPT_OFFER', 'ACCEPT_BID')"
    )
    op.execute(
        "CREATE TYPE approvalstatus AS ENUM "
        "('PENDING', 'APPROVED_EXECUTED', 'APPROVED_FAILED', 'REJECTED', 'EXPIRED', 'CANCELLED')"
    )

    op.create_table(
        "pending_approvals",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("club_id", sa.Uuid(as_uuid=True), sa.ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "action_type",
            pg.ENUM("PLACE_BID", "CREATE_OFFER", "ACCEPT_OFFER", "ACCEPT_BID",
                    name="approvalactiontype", create_type=False),
            nullable=False,
        ),
        sa.Column("payload_json", sa.JSON().with_variant(pg.JSONB, "postgresql"), nullable=False),
        sa.Column("amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("requested_by_user_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "status",
            pg.ENUM("PENDING", "APPROVED_EXECUTED", "APPROVED_FAILED", "REJECTED", "EXPIRED", "CANCELLED",
                    name="approvalstatus", create_type=False),
            nullable=False,
        ),
        sa.Column("decided_by_user_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_reason", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("summary", sa.String(500), nullable=True),
    )
    op.create_index("ix_pending_approvals_club_id", "pending_approvals", ["club_id"])
    op.create_index("ix_pending_approvals_requested_by_user_id", "pending_approvals", ["requested_by_user_id"])
    op.create_index("ix_pending_approvals_status", "pending_approvals", ["status"])


def downgrade() -> None:
    op.drop_table("pending_approvals")
    op.execute("DROP TYPE approvalstatus")
    op.execute("DROP TYPE approvalactiontype")
    op.drop_column("club_finances", "approval_threshold")
    # notificationtype enum value removal is a no-op in Postgres.
