"""Deadline-day mode: the DEADLINE_DAY notification

Revision ID: 0102
Revises: 0101
Create Date: 2026-10-17
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0102"
down_revision: Union[str, None] = "0101"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'DEADLINE_DAY'")


def downgrade() -> None:
    # Postgres can't drop an enum value; DEADLINE_DAY stays.
    pass
