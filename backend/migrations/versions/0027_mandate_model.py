"""Add agent_id to players; create mandates table.

Revision ID: 0027
Revises: 0026
Create Date: 2026-06-17
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0027"
down_revision: Union[str, None] = "0026"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "players",
        sa.Column(
            "agent_id",
            sa.Uuid(),
            sa.ForeignKey("agent_profiles.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_players_agent_id", "players", ["agent_id"])

    op.create_table(
        "mandates",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "agent_id",
            sa.Uuid(),
            sa.ForeignKey("agent_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "player_id",
            sa.Uuid(),
            sa.ForeignKey("players.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("exclusive", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("territory", sa.String(200), nullable=True),
        sa.Column(
            "status",
            sa.Enum("ACTIVE", "EXPIRED", "REVOKED", name="mandatestatus"),
            nullable=False,
            server_default="ACTIVE",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_mandates_agent_id", "mandates", ["agent_id"])
    op.create_index("ix_mandates_player_id", "mandates", ["player_id"])
    op.create_index("ix_mandates_status", "mandates", ["status"])


def downgrade() -> None:
    op.drop_index("ix_mandates_status", "mandates")
    op.drop_index("ix_mandates_player_id", "mandates")
    op.drop_index("ix_mandates_agent_id", "mandates")
    op.drop_table("mandates")
    op.execute("DROP TYPE IF EXISTS mandatestatus")
    op.drop_index("ix_players_agent_id", "players")
    op.drop_column("players", "agent_id")
