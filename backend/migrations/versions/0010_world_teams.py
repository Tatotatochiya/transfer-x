"""Add world_teams table and world_team_id FK on players.

Revision ID: 0010
Revises: 0009
Create Date: 2026-03-21
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "world_teams",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("vendor", sa.String(100), nullable=False),
        sa.Column("vendor_id", sa.String(200), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("country", sa.String(100), nullable=True),
        sa.Column("league_name", sa.String(200), nullable=True),
        sa.Column("crest_url", sa.String(500), nullable=True),
        sa.Column("season", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("vendor", "vendor_id", name="uq_world_teams_vendor_id"),
    )
    op.create_index("ix_world_teams_vendor", "world_teams", ["vendor"])
    op.create_index("ix_world_teams_name", "world_teams", ["name"])
    op.create_index("ix_world_teams_country", "world_teams", ["country"])
    op.create_index("ix_world_teams_season", "world_teams", ["season"])

    op.add_column(
        "players",
        sa.Column("world_team_id", sa.Uuid(as_uuid=True), sa.ForeignKey("world_teams.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("ix_players_world_team_id", "players", ["world_team_id"])


def downgrade() -> None:
    op.drop_index("ix_players_world_team_id", "players")
    op.drop_column("players", "world_team_id")
    op.drop_index("ix_world_teams_season", "world_teams")
    op.drop_index("ix_world_teams_country", "world_teams")
    op.drop_index("ix_world_teams_name", "world_teams")
    op.drop_index("ix_world_teams_vendor", "world_teams")
    op.drop_table("world_teams")
