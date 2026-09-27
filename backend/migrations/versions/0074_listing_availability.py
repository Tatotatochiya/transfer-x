"""Listing availability: transfer, loan, or either

A club could only list a player for sale. Clubs routinely make players
available on loan instead — young or surplus players — and buyers had no way
to know who was loanable. `availability` says what the seller will consider;
`sale_type` still says how offers arrive. Every existing listing was made as a
sale, so they backfill to TRANSFER.

Revision ID: 0074
Revises: 0073
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ENUM as PgEnum

revision: str = "0074"
down_revision: Union[str, None] = "0073"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE TYPE listingavailability AS ENUM ('TRANSFER', 'LOAN', 'EITHER')")
    op.add_column(
        "sales",
        sa.Column(
            "availability",
            PgEnum("TRANSFER", "LOAN", "EITHER", name="listingavailability", create_type=False),
            nullable=False,
            server_default="TRANSFER",
        ),
    )
    op.create_index("ix_sales_availability", "sales", ["availability"])


def downgrade() -> None:
    op.drop_index("ix_sales_availability", table_name="sales")
    op.drop_column("sales", "availability")
    op.execute("DROP TYPE listingavailability")
