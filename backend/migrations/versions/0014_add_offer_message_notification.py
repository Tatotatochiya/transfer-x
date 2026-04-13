"""Add OFFER_MESSAGE to notificationtype enum.

Revision ID: 0014
Revises: 0013
Create Date: 2026-03-28
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0014"
down_revision: Union[str, None] = "0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'OFFER_MESSAGE'")


def downgrade() -> None:
    pass
