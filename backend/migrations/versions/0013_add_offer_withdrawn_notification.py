"""Add OFFER_WITHDRAWN to notificationtype enum.

Revision ID: 0013
Revises: 0012
Create Date: 2026-03-28
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0013"
down_revision: Union[str, None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'OFFER_WITHDRAWN'")


def downgrade() -> None:
    # Postgres does not support removing enum values; downgrade is a no-op.
    pass
