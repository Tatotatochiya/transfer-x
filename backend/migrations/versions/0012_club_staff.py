"""Add club_staff table for per-club staff accounts.

Revision ID: 0012
Revises: 0011
Create Date: 2026-03-21
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ENUM as PgEnum

revision: str = "0012"
down_revision: Union[str, Sequence[str]] = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE staffrole AS ENUM ('MANAGER', 'READONLY');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)
    op.create_table(
        "club_staff",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("club_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column(
            "role",
            PgEnum("MANAGER", "READONLY", name="staffrole", create_type=False),
            nullable=False,
            server_default="READONLY",
        ),
        sa.Column("created_by_user_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["club_id"], ["clubs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("user_id", name="uq_club_staff_user_id"),
    )
    op.create_index("ix_club_staff_club_id", "club_staff", ["club_id"])
    op.create_index("ix_club_staff_user_id", "club_staff", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_club_staff_user_id", table_name="club_staff")
    op.drop_index("ix_club_staff_club_id", table_name="club_staff")
    op.drop_table("club_staff")
    op.execute("DROP TYPE IF EXISTS staffrole")
