"""Transfer windows per country, with where the dates came from

A window only governs registering a player at a club in its country, so
each window names one; a window with no country covers every club (the
windows created before this). Offers and deals now run all year: the
window holds completion, not negotiation (docs/product/workflows/
deal-completion.md).

Revision ID: 0108
Revises: 0107
Create Date: 2026-11-07
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0108"
down_revision: Union[str, None] = "0107"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("transfer_windows", sa.Column("country", sa.String(100), nullable=True))
    op.add_column("transfer_windows", sa.Column("source_url", sa.String(500), nullable=True))
    op.add_column("transfer_windows", sa.Column("checked_on", sa.Date(), nullable=True))
    op.add_column("transfer_windows", sa.Column("opened_notice_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_transfer_windows_country", "transfer_windows", ["country"])


def downgrade() -> None:
    op.drop_index("ix_transfer_windows_country", table_name="transfer_windows")
    op.drop_column("transfer_windows", "opened_notice_at")
    op.drop_column("transfer_windows", "checked_on")
    op.drop_column("transfer_windows", "source_url")
    op.drop_column("transfer_windows", "country")
