"""Clubs and leagues a listing excludes

`sales.excluded_club_ids` and `sales.excluded_leagues`, JSON lists, empty by
default. While the listing is open, an excluded club can't make an offer for
the player. Additive.

Revision ID: 0117
Revises: 0116
Create Date: 2026-11-28
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0117"
down_revision: Union[str, None] = "0116"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("sales", sa.Column("excluded_club_ids", sa.JSON(), nullable=False, server_default="[]"))
    op.add_column("sales", sa.Column("excluded_leagues", sa.JSON(), nullable=False, server_default="[]"))


def downgrade() -> None:
    op.drop_column("sales", "excluded_leagues")
    op.drop_column("sales", "excluded_club_ids")
