"""Real-world moves: the REAL_WORLD_MOVES notification for the club

Revision ID: 0103
Revises: 0102
Create Date: 2026-10-17
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0103"
down_revision: Union[str, None] = "0102"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'REAL_WORLD_MOVES'")


def downgrade() -> None:
    # Postgres can't drop an enum value; REAL_WORLD_MOVES stays.
    pass
