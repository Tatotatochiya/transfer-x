"""Move reminders: chase a stalled offer, deal or enquiry (docs/feature_spec/move-reminders).

Revision ID: 0111
Revises: 0110
Create Date: 2026-11-12
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0111"
down_revision: Union[str, None] = "0110"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "move_reminders",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("subject_type", sa.String(20), nullable=False),
        sa.Column("subject_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("move_key", sa.String(80), nullable=False),
        sa.Column("holder_kind", sa.String(10), nullable=False),
        sa.Column("holder_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("sender_user_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("sender_club_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("escalated", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("automatic", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("note", sa.String(200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_move_reminders_subject", "move_reminders", ["subject_type", "subject_id", "created_at"])
    op.execute("ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'MOVE_REMINDER'")
    op.execute("ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'MOVE_ESCALATED'")


def downgrade() -> None:
    # notificationtype enum values can't be removed in Postgres.
    op.drop_index("ix_move_reminders_subject", table_name="move_reminders")
    op.drop_table("move_reminders")
