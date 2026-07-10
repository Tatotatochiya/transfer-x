"""Gap-list item 14: add RELEASE_CLAUSE_TRIGGERED notification type.

Revision ID: 0057
Revises: 0056
Create Date: 2026-07-11
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0057"
down_revision: Union[str, None] = "0056"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'RELEASE_CLAUSE_TRIGGERED'")


def downgrade() -> None:
    # notificationtype enum value removal is a no-op in Postgres.
    pass
