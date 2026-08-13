"""Anonymous buying club on offers

A club can approach without disclosing who they are; the seller sees only the
buyer's league until the offer is accepted. Per-offer rather than per-club,
because it is a decision about a single approach — a club may be open about
one target and discreet about another.

Existing offers backfill to false: every offer made before this shipped was
made openly, and silently turning historic approaches anonymous would rewrite
what the counterparty already saw.

Revision ID: 0064
Revises: 0063
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0064"
down_revision: Union[str, None] = "0063"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "offers",
        sa.Column(
            "is_anonymous",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("offers", "is_anonymous")
