"""Add UserType to users; create agent_profiles and player_profiles tables.

Revision ID: 0026
Revises: 0025
Create Date: 2026-06-17
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0026"
down_revision: Union[str, None] = "0025"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE TYPE usertype AS ENUM ('CLUB', 'AGENT', 'PLAYER', 'STAFF', 'ADMIN')")
    op.add_column(
        "users",
        sa.Column(
            "user_type",
            sa.Enum("CLUB", "AGENT", "PLAYER", "STAFF", "ADMIN", name="usertype", create_type=False),
            nullable=False,
            server_default="CLUB",
        ),
    )
    op.create_table(
        "agent_profiles",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            unique=True,
            nullable=False,
        ),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("agency_name", sa.String(200), nullable=False),
        sa.Column("licence_no", sa.String(100), nullable=True),
        sa.Column("country", sa.String(100), nullable=False),
        sa.Column("verified", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_agent_profiles_user_id", "agent_profiles", ["user_id"])
    op.create_table(
        "player_profiles",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            unique=True,
            nullable=False,
        ),
        sa.Column(
            "player_id",
            sa.Uuid(),
            sa.ForeignKey("players.id", ondelete="CASCADE"),
            unique=True,
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_player_profiles_user_id", "player_profiles", ["user_id"])
    op.create_index("ix_player_profiles_player_id", "player_profiles", ["player_id"])


def downgrade() -> None:
    op.drop_index("ix_player_profiles_player_id", "player_profiles")
    op.drop_index("ix_player_profiles_user_id", "player_profiles")
    op.drop_table("player_profiles")
    op.drop_index("ix_agent_profiles_user_id", "agent_profiles")
    op.drop_table("agent_profiles")
    op.drop_column("users", "user_type")
    op.execute("DROP TYPE IF EXISTS usertype")
