"""TRA-151: extend staffrole enum with SPORTING_DIRECTOR and SCOUT.

Revision ID: 0049
Revises: 0048
Create Date: 2026-07-09
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0049"
down_revision: Union[str, None] = "0048"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE staffrole ADD VALUE IF NOT EXISTS 'SPORTING_DIRECTOR'")
    op.execute("ALTER TYPE staffrole ADD VALUE IF NOT EXISTS 'SCOUT'")


def downgrade() -> None:
    # Postgres cannot remove enum values; leaving them in place is harmless.
    pass
