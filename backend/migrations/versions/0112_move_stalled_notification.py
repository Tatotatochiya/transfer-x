"""MOVE_STALLED: the people told when a reminder escalates (docs/feature_spec/move-reminders).

Its own migration because 0111 had already shipped when this type was added.

Revision ID: 0112
Revises: 0111
Create Date: 2026-11-14
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0112"
down_revision: Union[str, None] = "0111"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'MOVE_STALLED'")


def downgrade() -> None:
    # Postgres can't drop an enum value; it stays, unused.
    pass
