"""At most one open listing per player

Nothing prevented a player being listed twice. It stayed latent while listing
meant a full-page form reached from one place; it stops being latent once a
player can be listed in two clicks from the squad and from his own page — a
fast double-click, or the same player listed from two tabs, would put two
public listings for him on the market.

A partial unique index rather than a router check alone: a check-then-insert
cannot stop two concurrent requests from both passing before either commits.
The router still checks first so the caller gets a readable 409.

Verified before writing that neither local nor Railway holds a player with two
open listings, so this creates cleanly on both.

Revision ID: 0070
Revises: 0069
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0070"
down_revision: Union[str, None] = "0069"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "uq_sales_one_open_per_player",
        "sales",
        ["player_id"],
        unique=True,
        postgresql_where=sa.text("status = 'OPEN'"),
    )


def downgrade() -> None:
    op.drop_index("uq_sales_one_open_per_player", table_name="sales")
