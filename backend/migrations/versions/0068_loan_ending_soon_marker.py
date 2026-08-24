"""Record when a loan's ending-soon warning was sent

Phase 3 of docs/feature_spec/loan-transfers.md.

The daily job warns both clubs two weeks before a loan ends, and must do so
once rather than every day for a fortnight. The first attempt inferred that
from the notifications table by comparing a notification's `created_at` against
the loan's — which is fragile: the two are set by different server defaults,
and under SQLite the comparison is between a Python datetime and a string, so
the guard silently never matched and the job re-warned on every run.

A marker on the loan itself is unambiguous, needs no cross-table reasoning, and
makes "has this loan warned yet" answerable by looking at the loan.

Revision ID: 0068
Revises: 0067
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0068"
down_revision: Union[str, None] = "0067"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "player_loans",
        sa.Column("ending_soon_notified_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("player_loans", "ending_soon_notified_at")
