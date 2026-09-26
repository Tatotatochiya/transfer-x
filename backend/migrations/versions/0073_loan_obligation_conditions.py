"""Obligation conditions on loans

A loan row copies the purchase terms it was agreed with (option price,
obligation) from its deal, so the loans panel can show them without reading the
deal. The obligation's conditions are now agreed on the offer (0072) and belong
with them: without this the panel said an obligation "completes automatically"
with no word of what it was conditional on.

Backfilled from each loan's deal.

Revision ID: 0073
Revises: 0072
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0073"
down_revision: Union[str, None] = "0072"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("player_loans", sa.Column("obligation_conditions", sa.Text(), nullable=True))
    op.execute(
        "UPDATE player_loans SET obligation_conditions = deals.obligation_conditions "
        "FROM deals WHERE deals.id = player_loans.deal_id AND player_loans.obligation_to_buy"
    )


def downgrade() -> None:
    op.drop_column("player_loans", "obligation_conditions")
