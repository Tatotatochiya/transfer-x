"""Lite L6: held sends for undo (architecture ADR 0007)

A confirmed Lite action (bid, counter, accept, reject) is held for 10
seconds before it is sent, so it can be undone before the other club is
told anything. The executor then runs the normal endpoint as the user who
confirmed it, and records the result.

Revision ID: 0090
Revises: 0089
Create Date: 2026-10-03
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0090"
down_revision: Union[str, None] = "0089"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

STATUS = postgresql.ENUM("HELD", "EXECUTED", "CANCELLED", "FAILED", name="heldactionstatus", create_type=False)
CHANNEL = postgresql.ENUM("APP", "EMAIL", name="heldactionchannel", create_type=False)


def upgrade() -> None:
    bind = op.get_bind()
    STATUS.create(bind, checkfirst=True)
    CHANNEL.create(bind, checkfirst=True)
    op.create_table(
        "held_actions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("club_id", sa.Uuid(), sa.ForeignKey("clubs.id", ondelete="CASCADE"), nullable=True),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("payload_json", postgresql.JSONB(), nullable=False),
        sa.Column("status", STATUS, nullable=False, index=True),
        sa.Column("execute_at", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("result_json", postgresql.JSONB(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("channel", CHANNEL, nullable=False, server_default="APP"),
        sa.Column("ai_assisted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("held_actions")
    bind = op.get_bind()
    CHANNEL.drop(bind, checkfirst=True)
    STATUS.drop(bind, checkfirst=True)
