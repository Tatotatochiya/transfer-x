"""Real-world moves: staff dismissals, and the REGISTRATION_UPDATED notification

Revision ID: 0101
Revises: 0100
Create Date: 2026-10-12
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0101"
down_revision: Union[str, None] = "0100"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'REGISTRATION_UPDATED'")
    op.create_table(
        "real_world_dismissals",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("player_id", sa.Uuid(), sa.ForeignKey("players.id", ondelete="CASCADE"), nullable=False),
        sa.Column("real_team_vendor_id", sa.String(50), nullable=False),
        sa.Column("real_club", sa.String(200), nullable=True),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("dismissed_by_user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("player_id", "real_team_vendor_id", name="uq_real_world_dismissal"),
    )
    op.create_index("ix_real_world_dismissals_player_id", "real_world_dismissals", ["player_id"])


def downgrade() -> None:
    op.drop_index("ix_real_world_dismissals_player_id", table_name="real_world_dismissals")
    op.drop_table("real_world_dismissals")
    # Postgres can't drop an enum value; REGISTRATION_UPDATED stays.
