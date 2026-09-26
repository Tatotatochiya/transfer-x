"""Exercise-option approval type

Exercising a loan's option to buy commits the club to the option price, so it
joins the other money actions behind D7 spending approval. One new
`approvalactiontype` value.

`ADD VALUE` cannot be reversed — Postgres has no DROP VALUE — so, as in 0067,
the downgrade is a documented no-op: a spare enum value is inert.

Revision ID: 0071
Revises: 0070
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0071"
down_revision: Union[str, None] = "0070"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE approvalactiontype ADD VALUE IF NOT EXISTS 'EXERCISE_OPTION'")


def downgrade() -> None:
    # Postgres cannot remove an enum value. Left in place deliberately.
    pass
