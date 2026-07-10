"""TRA-86: club staff invitations + STAFF_INVITATION notification type.

Revision ID: 0050
Revises: 0049
Create Date: 2026-07-10
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision: str = "0050"
down_revision: Union[str, None] = "0049"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'STAFF_INVITATION'")

    op.create_table(
        "club_staff_invitations",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("club_id", sa.Uuid(as_uuid=True), sa.ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column(
            "role",
            pg.ENUM("SPORTING_DIRECTOR", "MANAGER", "SCOUT", "READONLY", name="staffrole", create_type=False),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("invited_by_user_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_club_staff_invitations_club_id", "club_staff_invitations", ["club_id"])
    op.create_index("ix_club_staff_invitations_email", "club_staff_invitations", ["email"])
    op.create_index("ix_club_staff_invitations_token_hash", "club_staff_invitations", ["token_hash"])


def downgrade() -> None:
    op.drop_table("club_staff_invitations")
    # notificationtype enum value removal is a no-op in Postgres.
