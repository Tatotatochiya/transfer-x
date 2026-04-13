"""Add club_valuation to contracts.

Revision ID: 0018
Revises: 0017
Create Date: 2026-04-11
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0018"
down_revision: Union[str, None] = "0017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "contracts",
        sa.Column("club_valuation", sa.Numeric(15, 2), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("contracts", "club_valuation")
