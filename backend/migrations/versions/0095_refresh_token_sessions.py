"""Signed-in devices: a session per sign-in, carried across token refreshes

Revision ID: 0095
Revises: 0094
Create Date: 2026-10-04
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0095"
down_revision: Union[str, None] = "0094"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("refresh_tokens", sa.Column("session_id", sa.Uuid(), nullable=True))
    op.add_column("refresh_tokens", sa.Column("user_agent", sa.String(300), nullable=True))
    op.add_column("refresh_tokens", sa.Column("signed_in_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("refresh_tokens", sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True))
    # Existing sign-ins become one session each.
    op.execute("UPDATE refresh_tokens SET session_id = id, signed_in_at = created_at, last_used_at = created_at")
    op.alter_column("refresh_tokens", "session_id", nullable=False)
    op.create_index("ix_refresh_tokens_session_id", "refresh_tokens", ["session_id"])


def downgrade() -> None:
    op.drop_index("ix_refresh_tokens_session_id", table_name="refresh_tokens")
    op.drop_column("refresh_tokens", "last_used_at")
    op.drop_column("refresh_tokens", "signed_in_at")
    op.drop_column("refresh_tokens", "user_agent")
    op.drop_column("refresh_tokens", "session_id")
