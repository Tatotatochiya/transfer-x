"""Add analytics_events table.

Revision ID: 0017
Revises: 0016
Create Date: 2026-04-08
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM
from alembic import op

revision: str = "0017"
down_revision: Union[str, None] = "0016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Pre-existing enum type — create only if it doesn't already exist
_event_type_enum = ENUM(
    "PAGE_VIEW", "PAGE_LEAVE", "CLICK",
    name="analytics_event_type",
    create_type=False,
)


def upgrade() -> None:
    # Idempotent enum creation — safe to run even if the type already exists
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE analytics_event_type AS ENUM ('PAGE_VIEW', 'PAGE_LEAVE', 'CLICK');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$
    """)

    op.create_table(
        "analytics_events",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("session_id", sa.Uuid(as_uuid=True), nullable=False, index=True),
        sa.Column(
            "user_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(512), nullable=True),
        sa.Column("event_type", _event_type_enum, nullable=False, index=True),
        sa.Column("path", sa.String(512), nullable=False, index=True),
        sa.Column("referrer", sa.String(512), nullable=True),
        sa.Column("element", sa.String(256), nullable=True),
        sa.Column("duration_ms", sa.Integer, nullable=True),
        sa.Column("meta", sa.JSON, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
            index=True,
        ),
    )


def downgrade() -> None:
    op.drop_table("analytics_events")
    op.execute("DROP TYPE IF EXISTS analytics_event_type")
