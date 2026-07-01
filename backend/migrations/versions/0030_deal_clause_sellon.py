"""TRA-57: Add DealClause table and DEAL_SELL_ON notification type.

Revision ID: 0030
Revises: 0029
Create Date: 2026-06-20
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision: str = "0030"
down_revision: Union[str, None] = "0029"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE TYPE clausetype AS ENUM ('APPEARANCES', 'GOALS', 'PROMOTION', 'RESALE', 'OTHER')")
    op.execute("CREATE TYPE clausestatus AS ENUM ('PENDING', 'TRIGGERED', 'PAID')")

    op.create_table(
        "deal_clauses",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("deal_id", sa.Uuid(as_uuid=True), sa.ForeignKey("deals.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("clause_type", pg.ENUM("APPEARANCES", "GOALS", "PROMOTION", "RESALE", "OTHER", name="clausetype", create_type=False), nullable=False),
        sa.Column("trigger_description", sa.Text(), nullable=False),
        sa.Column("amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("cap", sa.Numeric(15, 2), nullable=True),
        sa.Column("status", pg.ENUM("PENDING", "TRIGGERED", "PAID", name="clausestatus", create_type=False), nullable=False, server_default="PENDING"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    op.execute("ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'DEAL_SELL_ON'")


def downgrade() -> None:
    op.drop_table("deal_clauses")
    op.execute("DROP TYPE clausetype")
    op.execute("DROP TYPE clausestatus")
    # PostgreSQL does not support removing enum values; DEAL_SELL_ON downgrade is a no-op.
