"""Add notification_preferences table.

Revision ID: 0011
Revises: 0010
Create Date: 2026-03-21
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: Union[str, Sequence[str]] = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Use raw SQL to reference the existing notificationtype enum without recreating it
    op.execute("""
        CREATE TABLE notification_preferences (
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            type notificationtype NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (user_id, type)
        )
    """)


def downgrade() -> None:
    op.drop_table("notification_preferences")
