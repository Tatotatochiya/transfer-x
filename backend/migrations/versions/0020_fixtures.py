"""Add fixtures table.

Revision ID: 0020
Revises: 0019
Create Date: 2026-04-12
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0020"
down_revision: Union[str, None] = "0019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "fixtures",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("vendor", sa.String(50), nullable=False),
        sa.Column("fixture_vendor_id", sa.Integer, nullable=False, index=True),
        sa.Column("league_id", sa.Integer, nullable=True, index=True),
        sa.Column("season", sa.Integer, nullable=True),
        sa.Column("league_name", sa.String(200), nullable=True),
        sa.Column("round", sa.String(100), nullable=True),
        sa.Column("home_team_vendor_id", sa.Integer, nullable=False, index=True),
        sa.Column("home_team_name", sa.String(200), nullable=False),
        sa.Column("home_team_crest_url", sa.String(512), nullable=True),
        sa.Column("away_team_vendor_id", sa.Integer, nullable=False, index=True),
        sa.Column("away_team_name", sa.String(200), nullable=False),
        sa.Column("away_team_crest_url", sa.String(512), nullable=True),
        sa.Column("kickoff_at", sa.DateTime(timezone=True), nullable=True, index=True),
        sa.Column("status_short", sa.String(10), nullable=False, server_default="NS"),
        sa.Column("status_long", sa.String(100), nullable=True),
        sa.Column("home_goals", sa.Integer, nullable=True),
        sa.Column("away_goals", sa.Integer, nullable=True),
        sa.Column("venue_name", sa.String(200), nullable=True),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("vendor", "fixture_vendor_id", name="uq_fixtures_vendor_fixture_id"),
    )


def downgrade() -> None:
    op.drop_table("fixtures")
