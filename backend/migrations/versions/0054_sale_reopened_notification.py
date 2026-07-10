"""Gap-list item 4: add SALE_REOPENED notification type (collapse restores the sale).

Revision ID: 0054
Revises: 0053
Create Date: 2026-07-11
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0054"
down_revision: Union[str, None] = "0053"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'SALE_REOPENED'")


def downgrade() -> None:
    # notificationtype enum value removal is a no-op in Postgres.
    pass
