"""TRA-132: agent_commissions table and CommissionStatus enum.

Revision ID: 0040
Revises: 0039
Create Date: 2026-06-20
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0040"
down_revision: Union[str, None] = "0039"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# CommissionPayer already exists from 0033; only CommissionStatus is new.
commission_status = postgresql.ENUM(
    "PENDING", "CONFIRMED", "INVOICED", "PAID",
    name="commissionstatus",
    create_type=True,
)


def upgrade() -> None:
    commission_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "agent_commissions",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("deal_id", sa.Uuid(as_uuid=True),
                  sa.ForeignKey("deals.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("agent_id", sa.Uuid(as_uuid=True),
                  sa.ForeignKey("agent_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("window_id", sa.Uuid(as_uuid=True),
                  sa.ForeignKey("transfer_windows.id", ondelete="SET NULL"), nullable=True),
        sa.Column("amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("pct", sa.Numeric(5, 4), nullable=True),
        sa.Column("payer", postgresql.ENUM("BUYER", "SELLER", "PLAYER", name="commissionpayer", create_type=False),
                  nullable=True),
        sa.Column("status", postgresql.ENUM("PENDING", "CONFIRMED", "INVOICED", "PAID",
                                    name="commissionstatus", create_type=False),
                  nullable=False, server_default="PENDING"),
        sa.Column("window_label", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("invoiced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_agent_commissions_deal_id", "agent_commissions", ["deal_id"])
    op.create_index("ix_agent_commissions_agent_id", "agent_commissions", ["agent_id"])
    op.create_index("ix_agent_commissions_window_id", "agent_commissions", ["window_id"])


def downgrade() -> None:
    op.drop_table("agent_commissions")
    commission_status.drop(op.get_bind(), checkfirst=True)
