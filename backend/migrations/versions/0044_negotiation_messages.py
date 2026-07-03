"""TRA-136: negotiation_messages table + NegotiationThread enum + NEGOTIATION_MESSAGE notification type.

Revision ID: 0044
Revises: 0043
Create Date: 2026-07-03
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision: str = "0044"
down_revision: Union[str, None] = "0043"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'NEGOTIATION_MESSAGE'")
    op.execute("CREATE TYPE negotiationthread AS ENUM ('CLUB_SIDE', 'PLAYER_SIDE')")

    op.create_table(
        "negotiation_messages",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column(
            "negotiation_id", sa.Uuid(as_uuid=True),
            sa.ForeignKey("agent_negotiations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "thread",
            pg.ENUM("CLUB_SIDE", "PLAYER_SIDE", name="negotiationthread", create_type=False),
            nullable=False,
        ),
        sa.Column(
            "sender_user_id", sa.Uuid(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
    )
    op.create_index("ix_negotiation_messages_negotiation_id", "negotiation_messages", ["negotiation_id"])
    op.create_index("ix_negotiation_messages_thread", "negotiation_messages", ["thread"])
    op.create_index("ix_negotiation_messages_created_at", "negotiation_messages", ["created_at"])


def downgrade() -> None:
    op.drop_table("negotiation_messages")
    op.execute("DROP TYPE negotiationthread")
    # notificationtype enum value removal is a no-op in Postgres.
