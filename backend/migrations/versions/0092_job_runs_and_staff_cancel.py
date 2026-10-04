"""Phase 0 loose ends: job history that survives restarts, staff-cancelled sales

- The admin Health page showed each scheduled job's last run from memory, so
  a restart (every deploy) wiped it. `scheduler_job_runs` keeps the last
  run, its outcome and its error per job.
- A sale cancelled by TransferX staff ended WITHDRAWN like a seller's own
  withdrawal. `sales.staff_cancel_reason` marks it and keeps the reason.

Revision ID: 0092
Revises: 0091
Create Date: 2026-10-03
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0092"
down_revision: Union[str, None] = "0091"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "scheduler_job_runs",
        sa.Column("job_id", sa.String(100), primary_key=True),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_ok", sa.Boolean(), nullable=False),
        sa.Column("last_error", sa.String(300), nullable=True),
        sa.Column("last_failure_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("sales", sa.Column("staff_cancel_reason", sa.String(500), nullable=True))


def downgrade() -> None:
    op.drop_column("sales", "staff_cancel_reason")
    op.drop_table("scheduler_job_runs")
