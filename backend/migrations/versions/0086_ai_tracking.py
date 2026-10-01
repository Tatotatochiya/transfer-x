"""AI suggestion events and Ask questions

`ai_suggestion_events`: each assistant suggestion SHOWN to a user, and each
one USED, so the admin AI page can show which features are used or ignored.
`assistant_queries`: each Ask question with how it was asked (text or voice)
and answered (links, a proposal, or a fallback).

Revision ID: 0086
Revises: 0085
Create Date: 2026-10-01
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0086"
down_revision: Union[str, None] = "0085"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ai_suggestion_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("feature", sa.String(50), nullable=False),
        sa.Column("event", sa.String(10), nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("ref", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_ai_suggestion_events_feature", "ai_suggestion_events", ["feature"])
    op.create_index("ix_ai_suggestion_events_user_id", "ai_suggestion_events", ["user_id"])
    op.create_index("ix_ai_suggestion_events_created_at", "ai_suggestion_events", ["created_at"])
    op.create_table(
        "assistant_queries",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("question", sa.String(500), nullable=False),
        sa.Column("input", sa.String(10), nullable=False, server_default="text"),
        sa.Column("lite", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("had_proposal", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("links_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("fallback", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_assistant_queries_user_id", "assistant_queries", ["user_id"])
    op.create_index("ix_assistant_queries_created_at", "assistant_queries", ["created_at"])


def downgrade() -> None:
    op.drop_table("assistant_queries")
    op.drop_table("ai_suggestion_events")
