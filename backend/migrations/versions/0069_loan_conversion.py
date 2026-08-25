"""Loan conversion to a permanent deal

Phase 4 of docs/feature_spec/loan-transfers.md.

`conversion_deal_id` links a loan to the permanent deal it produced, whether
the loanee exercised an option or an obligation crystallised at expiry. It is
the guard that stops the daily job creating a second deal for the same
obligation on every run, and it gives both clubs a link from the loan to the
deal that is now settling it.

`LOAN_CONVERTED` tells both clubs a loan is becoming permanent. As with 0067,
Postgres cannot remove an enum value, so the downgrade drops only the column.

Revision ID: 0069
Revises: 0068
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0069"
down_revision: Union[str, None] = "0068"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "player_loans",
        sa.Column(
            "conversion_deal_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("deals.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.execute("ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'LOAN_CONVERTED'")


def downgrade() -> None:
    op.drop_column("player_loans", "conversion_deal_id")
    # Postgres cannot remove an enum value; LOAN_CONVERTED stays, inert.
