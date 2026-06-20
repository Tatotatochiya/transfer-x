"""TRA-59: Agent commission fields on deals table.

Revision ID: 0036
Revises: 0035
Create Date: 2026-06-20
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0036"
down_revision: Union[str, None] = "0035"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("deals", sa.Column("agent_commission_pct", sa.Numeric(5, 4), nullable=True))
    op.add_column("deals", sa.Column("agent_commission_amount", sa.Numeric(15, 2), nullable=True))
    op.add_column(
        "deals",
        sa.Column(
            "commission_payer",
            sa.Enum("BUYER", "SELLER", "PLAYER", name="commissionpayer"),
            nullable=True,
        ),
    )
    op.add_column(
        "deals",
        sa.Column(
            "commission_agent_id", sa.Uuid(as_uuid=True),
            sa.ForeignKey("agent_profiles.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("deals", "commission_agent_id")
    op.drop_column("deals", "commission_payer")
    op.drop_column("deals", "agent_commission_amount")
    op.drop_column("deals", "agent_commission_pct")
