"""Gap-list item 11: add REPRESENTATION_EXPIRED notification type.

Revision ID: 0052
Revises: 0051
Create Date: 2026-07-10
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0052"
down_revision: Union[str, None] = "0051"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'REPRESENTATION_EXPIRED'")


def downgrade() -> None:
    # notificationtype enum value removal is a no-op in Postgres.
    pass
