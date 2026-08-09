"""M9: fee_disclosed column, loan_fee + wage_weekly split on deals.

Revision ID: 0060
Revises: 0059
Create Date: 2026-07-12
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0060"
down_revision: Union[str, None] = "0059"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("deals", sa.Column("fee_disclosed", sa.Boolean(), nullable=True))
    op.add_column("deals", sa.Column("loan_fee", sa.Numeric(15, 2), nullable=True))
    op.add_column("deals", sa.Column("option_to_buy", sa.Numeric(15, 2), nullable=True))


def downgrade() -> None:
    op.drop_column("deals", "option_to_buy")
    op.drop_column("deals", "loan_fee")
    op.drop_column("deals", "fee_disclosed")
