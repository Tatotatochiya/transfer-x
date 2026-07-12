"""Re-audit fixes: WAIVED medical status, deal confirmed_at + option_exercised,
transfer_windows grace_period_hours.

- MedicalStatus gains WAIVED (buying club can explicitly waive a medical, which
  now — like PASSED — satisfies the "medical recorded" requirement before
  PAPERWORK can be confirmed).
- deals.confirmed_at records when a deal reached CONFIRMED, used to grant a
  deadline-day grace period for completing after the transfer window closes.
- deals.option_exercised makes exercising a loan's purchase option one-shot.
- transfer_windows.grace_period_hours configures that grace period per window.

Revision ID: 0061
Revises: 0060
Create Date: 2026-07-12
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0061"
down_revision: Union[str, None] = "0060"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE medicalstatus ADD VALUE IF NOT EXISTS 'WAIVED'")

    op.add_column(
        "deals",
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "deals",
        sa.Column("option_exercised", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "transfer_windows",
        sa.Column("grace_period_hours", sa.Integer(), nullable=False, server_default="24"),
    )


def downgrade() -> None:
    op.drop_column("transfer_windows", "grace_period_hours")
    op.drop_column("deals", "option_exercised")
    op.drop_column("deals", "confirmed_at")
    # medicalstatus enum value removal is a no-op in Postgres.
