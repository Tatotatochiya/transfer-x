"""Gap-list item 13 (scoped): FREE_TRANSFER and PRE_CONTRACT deal types.

Revision ID: 0058
Revises: 0057
Create Date: 2026-07-11
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0058"
down_revision: Union[str, None] = "0057"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE dealtype ADD VALUE IF NOT EXISTS 'FREE_TRANSFER'")
    op.execute("ALTER TYPE dealtype ADD VALUE IF NOT EXISTS 'PRE_CONTRACT'")


def downgrade() -> None:
    # dealtype enum value removal is a no-op in Postgres.
    pass
