"""Deals collapse at the buying club's window close (product ADR 0014)

`deals.expires_at` (when it collapses unless completed) and
`deals.expiry_warned_at` (the day-before warning was sent), and the
DEAL_EXPIRING notification type. Open deals get their date from the job
`expire_deals`, which fills it on its first run. Additive.

Revision ID: 0118
Revises: 0117
Create Date: 2026-11-28
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0118"
down_revision: Union[str, None] = "0117"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("deals", sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("deals", sa.Column("expiry_warned_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_deals_expires_at", "deals", ["expires_at"])
    op.execute("ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'DEAL_EXPIRING'")


def downgrade() -> None:
    # Postgres can't drop an enum value; DEAL_EXPIRING stays, unused.
    op.drop_index("ix_deals_expires_at", table_name="deals")
    op.drop_column("deals", "expiry_warned_at")
    op.drop_column("deals", "expires_at")
