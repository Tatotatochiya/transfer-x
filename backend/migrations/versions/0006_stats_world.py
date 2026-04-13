"""Stats (player_stats, player_stats_snapshots, player_forms, vendor_sync_states) and World (world_leagues) tables.

Revision ID: 0006
Revises: 0005
Create Date: 2026-03-17
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── world_leagues ─────────────────────────────────────────────────────────
    op.create_table(
        "world_leagues",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("vendor", sa.String(length=100), nullable=False),
        sa.Column("league_id", sa.String(length=200), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("country", sa.String(length=100), nullable=True),
        sa.Column("season", sa.String(length=20), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("vendor", "league_id", name="uq_world_leagues_vendor_league"),
    )
    op.create_index(op.f("ix_world_leagues_vendor"), "world_leagues", ["vendor"])
    op.create_index(op.f("ix_world_leagues_country"), "world_leagues", ["country"])
    op.create_index(op.f("ix_world_leagues_season"), "world_leagues", ["season"])

    # ── player_stats ──────────────────────────────────────────────────────────
    op.create_table(
        "player_stats",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("player_id", sa.Uuid(), nullable=False),
        sa.Column("vendor", sa.String(length=100), nullable=False),
        sa.Column("league_id", sa.String(length=200), nullable=True),
        sa.Column("season", sa.String(length=20), nullable=True),
        sa.Column("goals", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("assists", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("appearances", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("avg_rating", sa.Numeric(4, 2), nullable=True),
        sa.Column("form_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_player_stats_player_id"), "player_stats", ["player_id"])

    # ── player_stats_snapshots ────────────────────────────────────────────────
    op.create_table(
        "player_stats_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("player_id", sa.Uuid(), nullable=False),
        sa.Column("vendor", sa.String(length=100), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_player_stats_snapshots_player_id"), "player_stats_snapshots", ["player_id"])

    # ── player_forms ──────────────────────────────────────────────────────────
    op.create_table(
        "player_forms",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("player_id", sa.Uuid(), nullable=False),
        sa.Column("form_score", sa.Numeric(5, 2), nullable=False),
        sa.Column("games_considered", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("key_metrics", sa.JSON(), nullable=True),
        sa.Column("last_updated", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("player_id", name="uq_player_forms_player_id"),
    )
    op.create_index(op.f("ix_player_forms_player_id"), "player_forms", ["player_id"])

    # ── vendor_sync_states ────────────────────────────────────────────────────
    op.create_table(
        "vendor_sync_states",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("vendor", sa.String(length=100), nullable=False),
        sa.Column("last_sync_at", sa.DateTime(), nullable=True),
        sa.Column("last_success_at", sa.DateTime(), nullable=True),
        sa.Column("last_error", sa.String(length=1000), nullable=True),
        sa.Column("error_count", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("vendor", name="uq_vendor_sync_states_vendor"),
    )


def downgrade() -> None:
    op.drop_table("vendor_sync_states")

    op.drop_index(op.f("ix_player_forms_player_id"), table_name="player_forms")
    op.drop_table("player_forms")

    op.drop_index(op.f("ix_player_stats_snapshots_player_id"), table_name="player_stats_snapshots")
    op.drop_table("player_stats_snapshots")

    op.drop_index(op.f("ix_player_stats_player_id"), table_name="player_stats")
    op.drop_table("player_stats")

    op.drop_index(op.f("ix_world_leagues_season"), table_name="world_leagues")
    op.drop_index(op.f("ix_world_leagues_country"), table_name="world_leagues")
    op.drop_index(op.f("ix_world_leagues_vendor"), table_name="world_leagues")
    op.drop_table("world_leagues")
