"""Gap-list item 5: deal completion SLA fields.

Revision ID: 0055
Revises: 0054
Create Date: 2026-07-11
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0055"
down_revision: Union[str, None] = "0054"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("deals", sa.Column("sla_deadline", sa.DateTime(timezone=True), nullable=True))
    op.add_column("deals", sa.Column("sla_escalated_at", sa.DateTime(timezone=True), nullable=True))
    op.execute("ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'DEAL_SLA_BREACHED'")


def downgrade() -> None:
    # notificationtype enum value removal is a no-op in Postgres.
    op.drop_column("deals", "sla_escalated_at")
    op.drop_column("deals", "sla_deadline")
