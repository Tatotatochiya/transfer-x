"""Conversation reads: when each person last read a transfer's conversation

Gives the deal and offer pages an unread count on Messages. One row per
person per conversation (player + buying club). No backfill: with no row,
every message from someone else counts as unread until the first read,
except that the count only looks back 14 days (see
conversation/service.unread_count).

Revision ID: 0110
Revises: 0109
Create Date: 2026-11-09
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0110"
down_revision: Union[str, None] = "0109"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "conversation_reads",
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("player_id", sa.Uuid(), sa.ForeignKey("players.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("buyer_club_id", sa.Uuid(), sa.ForeignKey("clubs.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("conversation_reads")
