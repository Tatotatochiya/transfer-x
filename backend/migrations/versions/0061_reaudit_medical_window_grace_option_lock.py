"""Re-audit fixes: WAIVED medical status, deal confirmed_at + option_exercised,
transfer_windows grace_period_hours.

Revision ID: 0061
Revises: 0060
Create Date: 2026-07-12
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0061"
down_revision: Union[str, None] = "0060"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("deals", sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("deals", sa.Column("option_exercised", sa.Boolean(), nullable=True))
    op.add_column("transfer_windows", sa.Column("grace_period_hours", sa.Integer(), nullable=True))
    # WAIVED added to medicalstatus enum — handled by SQLAlchemy enum auto-create


def downgrade() -> None:
    op.drop_column("transfer_windows", "grace_period_hours")
    op.drop_column("deals", "option_exercised")
    op.drop_column("deals", "confirmed_at")
