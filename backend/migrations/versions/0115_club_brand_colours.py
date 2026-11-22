"""A club's own colours, for its Dashboard band

`brand_primary` and `brand_secondary`, each '#RRGGBB' or null, set by a club
admin from My Club. Null is the default: the band is then a plain white card.
Additive and nullable.

Revision ID: 0115
Revises: 0114
Create Date: 2026-11-22
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0115"
down_revision: Union[str, None] = "0114"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("clubs", sa.Column("brand_primary", sa.String(7), nullable=True))
    op.add_column("clubs", sa.Column("brand_secondary", sa.String(7), nullable=True))


def downgrade() -> None:
    op.drop_column("clubs", "brand_secondary")
    op.drop_column("clubs", "brand_primary")
