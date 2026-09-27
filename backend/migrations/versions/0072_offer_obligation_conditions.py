"""Obligation conditions on offers

An obligation to buy is usually conditional ("if promoted", "after 20
appearances"). `deals.obligation_conditions` has existed since 0029, but the
only way to fill it was editing the deal after acceptance — which is now
refused, since a deal's loan terms are the ones agreed on the offer. So the
conditions are agreed on the offer, like every other loan term, and carried
onto the deal when it is accepted.

Revision ID: 0072
Revises: 0071
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0072"
down_revision: Union[str, None] = "0071"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("offers", sa.Column("obligation_conditions", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("offers", "obligation_conditions")
