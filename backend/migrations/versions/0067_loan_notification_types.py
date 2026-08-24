"""Loan notification types

Phase 3 of docs/feature_spec/loan-transfers.md.

Four new `notificationtype` values so the loan lifecycle can tell both clubs
what happened: the loan starting, ending within two weeks, ending, and being
recalled early.

`ADD VALUE` cannot run inside a transaction on older Postgres, and cannot be
reversed at all — Postgres has no DROP VALUE. The downgrade is therefore a
documented no-op rather than a lie: a spare enum value is inert, and rebuilding
the type would mean rewriting every notifications row.

Revision ID: 0067
Revises: 0066
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0067"
down_revision: Union[str, None] = "0066"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for value in ("LOAN_STARTED", "LOAN_ENDING_SOON", "LOAN_ENDED", "LOAN_RECALLED"):
        op.execute(f"ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS '{value}'")


def downgrade() -> None:
    # Postgres cannot remove an enum value. Left in place deliberately.
    pass
