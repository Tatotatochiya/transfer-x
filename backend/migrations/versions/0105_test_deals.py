"""Deals marked as tests, left out of shared figures

Revision ID: 0105
Revises: 0104
Create Date: 2026-10-29
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0105"
down_revision: Union[str, None] = "0104"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("deals", sa.Column("is_test", sa.Boolean(), nullable=False, server_default="false"))


def downgrade() -> None:
    op.drop_column("deals", "is_test")
