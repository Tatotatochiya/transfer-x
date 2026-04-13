"""Add team_name denormalized field to players.

Revision ID: 0009
Revises: 17e5dc6d7ccc
Create Date: 2026-03-21
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: Union[str, None] = "17e5dc6d7ccc"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("players", sa.Column("team_name", sa.String(200), nullable=True))


def downgrade() -> None:
    op.drop_column("players", "team_name")
