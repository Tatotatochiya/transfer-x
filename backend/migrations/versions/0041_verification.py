"""TRA-89: verification requests + verified flags on club/agent/player.

Revision ID: 0041
Revises: 0040
Create Date: 2026-07-03
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision: str = "0041"
down_revision: Union[str, None] = "0040"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "clubs", sa.Column("verified", sa.Boolean(), nullable=False, server_default="false")
    )
    op.add_column(
        "player_profiles", sa.Column("verified", sa.Boolean(), nullable=False, server_default="false")
    )

    op.execute("ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'VERIFICATION_APPROVED'")
    op.execute("ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'VERIFICATION_REJECTED'")

    op.execute("CREATE TYPE verificationentitytype AS ENUM ('CLUB', 'AGENT', 'PLAYER')")
    op.execute("CREATE TYPE verificationstatus AS ENUM ('PENDING', 'APPROVED', 'REJECTED')")

    op.create_table(
        "verification_requests",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column(
            "entity_type",
            pg.ENUM("CLUB", "AGENT", "PLAYER", name="verificationentitytype", create_type=False),
            nullable=False,
        ),
        sa.Column("entity_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column(
            "requested_by_user_id", sa.Uuid(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column(
            "status",
            pg.ENUM("PENDING", "APPROVED", "REJECTED", name="verificationstatus", create_type=False),
            nullable=False, server_default="PENDING",
        ),
        sa.Column("evidence_ref", sa.String(500), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column(
            "reviewed_by_user_id", sa.Uuid(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_notes", sa.Text, nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
    )
    op.create_index("ix_verification_requests_entity_type", "verification_requests", ["entity_type"])
    op.create_index("ix_verification_requests_entity_id", "verification_requests", ["entity_id"])
    op.create_index("ix_verification_requests_status", "verification_requests", ["status"])
    op.create_index("ix_verification_requests_created_at", "verification_requests", ["created_at"])


def downgrade() -> None:
    op.drop_table("verification_requests")
    op.execute("DROP TYPE verificationstatus")
    op.execute("DROP TYPE verificationentitytype")
    op.drop_column("player_profiles", "verified")
    op.drop_column("clubs", "verified")
    # notificationtype enum value removal is a no-op in Postgres.
