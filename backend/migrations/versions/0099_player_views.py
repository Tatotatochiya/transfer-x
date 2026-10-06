"""AI analyst: how often clubs view a player (counts per club per day)

Revision ID: 0099
Revises: 0098
Create Date: 2026-10-06
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0099"
down_revision: Union[str, None] = "0098"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "player_views",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("club_id", sa.Uuid(), sa.ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("player_id", sa.Uuid(), sa.ForeignKey("players.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("day", sa.Date(), nullable=False, index=True),
        sa.Column("count", sa.Integer(), nullable=False, server_default="1"),
        sa.UniqueConstraint("club_id", "player_id", "day", name="uq_player_views_club_player_day"),
    )


def downgrade() -> None:
    op.drop_table("player_views")
