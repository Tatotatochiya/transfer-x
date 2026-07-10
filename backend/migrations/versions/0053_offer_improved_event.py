"""Gap-list item 2: add IMPROVED offer event type (self-raise turn exception).

Revision ID: 0053
Revises: 0052
Create Date: 2026-07-10
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0053"
down_revision: Union[str, None] = "0052"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE offereventtype ADD VALUE IF NOT EXISTS 'IMPROVED'")


def downgrade() -> None:
    # offereventtype enum value removal is a no-op in Postgres.
    pass
