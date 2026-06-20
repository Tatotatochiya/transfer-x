"""TRA-56: Add deal_type (PERMANENT/LOAN) and loan fields to deals table.

Revision ID: 0029
Revises: 0028
Create Date: 2026-06-20
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0029"
down_revision: Union[str, None] = "0028"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE TYPE dealtype AS ENUM ('PERMANENT', 'LOAN')")
    op.add_column("deals", sa.Column(
        "deal_type",
        sa.Enum("PERMANENT", "LOAN", name="dealtype"),
        nullable=False,
        server_default="PERMANENT",
    ))
    op.add_column("deals", sa.Column("loan_start", sa.Date(), nullable=True))
    op.add_column("deals", sa.Column("loan_end", sa.Date(), nullable=True))
    op.add_column("deals", sa.Column("loan_fee", sa.Numeric(15, 2), nullable=True))
    op.add_column("deals", sa.Column("option_to_buy", sa.Numeric(15, 2), nullable=True))
    op.add_column("deals", sa.Column(
        "obligation_to_buy", sa.Boolean(), nullable=False, server_default="false"
    ))
    op.add_column("deals", sa.Column("obligation_conditions", sa.Text(), nullable=True))
    op.add_column("deals", sa.Column("sell_on_pct", sa.Numeric(5, 4), nullable=True))


def downgrade() -> None:
    op.drop_column("deals", "sell_on_pct")
    op.drop_column("deals", "obligation_conditions")
    op.drop_column("deals", "obligation_to_buy")
    op.drop_column("deals", "option_to_buy")
    op.drop_column("deals", "loan_fee")
    op.drop_column("deals", "loan_end")
    op.drop_column("deals", "loan_start")
    op.drop_column("deals", "deal_type")
    op.execute("DROP TYPE dealtype")
