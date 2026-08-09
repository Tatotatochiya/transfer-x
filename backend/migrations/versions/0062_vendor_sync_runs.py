"""Add vendor_sync_runs table — per-run history/breakdown for admin sync tracking.

Revision ID: 0062
Revises: 0061
Create Date: 2026-08-08
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0062"
down_revision: Union[str, None] = "0061"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "vendor_sync_runs",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("vendor", sa.String(100), nullable=False),
        sa.Column("operation", sa.String(50), nullable=False),
        sa.Column("params", sa.JSON, nullable=True),
        sa.Column("success", sa.Boolean, nullable=False),
        sa.Column("result", sa.JSON, nullable=True),
        sa.Column("error", sa.String(2000), nullable=True),
        sa.Column("triggered_by_user_id", sa.Uuid(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_ms", sa.Integer, nullable=False),
    )
    op.create_index("ix_vendor_sync_runs_vendor", "vendor_sync_runs", ["vendor"])
    op.create_index("ix_vendor_sync_runs_started_at", "vendor_sync_runs", ["started_at"])


def downgrade() -> None:
    op.drop_table("vendor_sync_runs")
