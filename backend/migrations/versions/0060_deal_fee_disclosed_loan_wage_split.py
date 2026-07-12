"""M9: add fee_disclosed and seller_wage_contribution_weekly to deals.

fee_disclosed (default true) — clubs may suppress exact fee from the public
transfer feed; existing deals default to disclosed (no data migration needed).

seller_wage_contribution_weekly — captures the seller's portion of the player's
weekly wage during a loan deal (informational; affects buyer net-wage accounting
at deal completion).

Revision ID: 0060
Revises: 0059
Create Date: 2026-07-12
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0060"
down_revision: Union[str, None] = "0059"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "deals",
        sa.Column("fee_disclosed", sa.Boolean(), nullable=False, server_default="true"),
    )
    op.add_column(
        "deals",
        sa.Column("seller_wage_contribution_weekly", sa.Numeric(15, 2), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("deals", "seller_wage_contribution_weekly")
    op.drop_column("deals", "fee_disclosed")
