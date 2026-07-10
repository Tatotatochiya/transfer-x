"""Gap-list item 8: private per-club channels in the deal room.

Revision ID: 0056
Revises: 0055
Create Date: 2026-07-11
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision: str = "0056"
down_revision: Union[str, None] = "0055"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE TYPE commentaudience AS ENUM ('SHARED', 'BUYER_ONLY', 'SELLER_ONLY')")

    audience_col = pg.ENUM(
        "SHARED", "BUYER_ONLY", "SELLER_ONLY", name="commentaudience", create_type=False
    )
    op.add_column(
        "deal_comments",
        sa.Column("audience", audience_col, nullable=False, server_default="SHARED"),
    )
    op.add_column(
        "deal_attachments",
        sa.Column("audience", audience_col, nullable=False, server_default="SHARED"),
    )


def downgrade() -> None:
    op.drop_column("deal_attachments", "audience")
    op.drop_column("deal_comments", "audience")
    op.execute("DROP TYPE commentaudience")
