"""Both clubs confirm a conditional obligation to buy

A conditional obligation ("if promoted") used to start the purchase at the
end of the loan regardless, and the clubs collapsed the deal if the condition
had not been met. Now it starts only when both clubs confirm the conditions
were met (product decision, 2026-09-28); both saying not met returns the
player. Each club's answer, and when they were prompted at expiry.

Revision ID: 0084
Revises: 0083
Create Date: 2026-09-28
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0084"
down_revision: Union[str, None] = "0083"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("player_loans", sa.Column("parent_obligation_answer", sa.String(10), nullable=True))
    op.add_column("player_loans", sa.Column("loanee_obligation_answer", sa.String(10), nullable=True))
    op.add_column("player_loans", sa.Column("obligation_prompted_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("player_loans", "obligation_prompted_at")
    op.drop_column("player_loans", "loanee_obligation_answer")
    op.drop_column("player_loans", "parent_obligation_answer")
