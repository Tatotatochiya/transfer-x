"""Enquiries — the informal first step before an offer

A club asks the owning club about a player ("is he available, what would it
take?") in a thread that commits nobody to anything, optionally without
naming itself. An offer reserves budget and may need approval; an enquiry
does neither. Two tables, a status enum, and two notification types
(ENQUIRY_RECEIVED, ENQUIRY_REPLIED — which, as in 0067, cannot be removed on
downgrade).

Revision ID: 0080
Revises: 0079
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ENUM as PgEnum

revision: str = "0080"
down_revision: Union[str, None] = "0079"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'ENQUIRY_RECEIVED'")
    op.execute("ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'ENQUIRY_REPLIED'")
    op.execute("CREATE TYPE enquirystatus AS ENUM ('OPEN', 'CLOSED')")
    op.create_table(
        "enquiries",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("player_id", sa.Uuid(), sa.ForeignKey("players.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("from_club_id", sa.Uuid(), sa.ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("to_club_id", sa.Uuid(), sa.ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("is_anonymous", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("status", PgEnum("OPEN", "CLOSED", name="enquirystatus", create_type=False),
                  nullable=False, server_default="OPEN", index=True),
        sa.Column("last_actor_club_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "enquiry_messages",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("enquiry_id", sa.Uuid(), sa.ForeignKey("enquiries.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("sender_club_id", sa.Uuid(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("enquiry_messages")
    op.drop_table("enquiries")
    op.execute("DROP TYPE enquirystatus")
