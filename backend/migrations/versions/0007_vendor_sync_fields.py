"""Add minutes to player_stats and trend to player_forms.

Revision ID: 0007
Revises: 0006
Create Date: 2026-03-17
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("player_stats", sa.Column("minutes", sa.Integer(), nullable=True))
    op.add_column("player_forms", sa.Column("trend", sa.Numeric(5, 2), nullable=True))


def downgrade() -> None:
    op.drop_column("player_forms", "trend")
    op.drop_column("player_stats", "minutes")
