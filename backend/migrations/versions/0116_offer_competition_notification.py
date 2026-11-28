"""OFFER_COMPETITION: another club's offer changed a buyer's place among the offers for a player.

Revision ID: 0116
Revises: 0115
Create Date: 2026-11-28
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0116"
down_revision: Union[str, None] = "0115"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'OFFER_COMPETITION'")


def downgrade() -> None:
    # Postgres can't drop an enum value; it stays, unused.
    pass
