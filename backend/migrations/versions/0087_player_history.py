"""Player profile ledger: season history from API-Football

`player_stats` gains the competition and club labels and a loan flag for
each row; `player_injuries` gains the end of the absence. New tables hold
the matches a player missed (`player_injury_fixtures`), his recent match
ratings (`player_fixture_ratings`), each club's matches per
competition-season (`team_season_fixtures`), and what the backfill has
fetched (`vendor_fetch_log`), so it can resume.

Revision ID: 0087
Revises: 0086
Create Date: 2026-10-01
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0087"
down_revision: Union[str, None] = "0086"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("player_stats", sa.Column("league_name", sa.String(200), nullable=True))
    op.add_column("player_stats", sa.Column("league_logo", sa.String(512), nullable=True))
    op.add_column("player_stats", sa.Column("team_logo", sa.String(512), nullable=True))
    op.add_column("player_stats", sa.Column("is_loan", sa.Boolean(), nullable=True))
    op.add_column("player_injuries", sa.Column("end_date", sa.Date(), nullable=True))

    op.create_table(
        "player_injury_fixtures",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("player_id", sa.Uuid(), sa.ForeignKey("players.id", ondelete="CASCADE"), nullable=False),
        sa.Column("fixture_vendor_id", sa.String(50), nullable=False),
        sa.Column("fixture_date", sa.Date(), nullable=True),
        sa.Column("league_id", sa.String(50), nullable=True),
        sa.Column("league_name", sa.String(200), nullable=True),
        sa.Column("season", sa.String(20), nullable=True),
        sa.Column("team_vendor_id", sa.String(50), nullable=True),
        sa.Column("injury_type", sa.String(100), nullable=True),
        sa.Column("reason", sa.String(200), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("player_id", "fixture_vendor_id", name="uq_injury_fixture_player"),
    )
    op.create_index("ix_player_injury_fixtures_player_id", "player_injury_fixtures", ["player_id"])

    op.create_table(
        "player_fixture_ratings",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("player_id", sa.Uuid(), sa.ForeignKey("players.id", ondelete="CASCADE"), nullable=False),
        sa.Column("fixture_vendor_id", sa.String(50), nullable=False),
        sa.Column("fixture_date", sa.Date(), nullable=True),
        sa.Column("league_name", sa.String(200), nullable=True),
        sa.Column("team_vendor_id", sa.String(50), nullable=True),
        sa.Column("opponent_name", sa.String(200), nullable=True),
        sa.Column("opponent_logo", sa.String(512), nullable=True),
        sa.Column("home", sa.Boolean(), nullable=True),
        sa.Column("minutes", sa.Integer(), nullable=True),
        sa.Column("rating", sa.Numeric(4, 2), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("player_id", "fixture_vendor_id", name="uq_fixture_rating_player"),
    )
    op.create_index("ix_player_fixture_ratings_player_id", "player_fixture_ratings", ["player_id"])

    op.create_table(
        "team_season_fixtures",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("team_vendor_id", sa.String(50), nullable=False),
        sa.Column("league_id", sa.String(50), nullable=False),
        sa.Column("season", sa.String(20), nullable=False),
        sa.Column("played", sa.Integer(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("team_vendor_id", "league_id", "season", name="uq_team_season_fixtures"),
    )

    op.create_table(
        "vendor_fetch_log",
        sa.Column("key", sa.String(200), primary_key=True),
        sa.Column("results", sa.Integer(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("vendor_fetch_log")
    op.drop_table("team_season_fixtures")
    op.drop_table("player_fixture_ratings")
    op.drop_table("player_injury_fixtures")
    op.drop_column("player_injuries", "end_date")
    for col in ("is_loan", "team_logo", "league_logo", "league_name"):
        op.drop_column("player_stats", col)
