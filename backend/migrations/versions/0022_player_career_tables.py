"""Add player_transfers and player_injuries tables.

Revision ID: 0022
Revises: 0021
Create Date: 2026-04-12
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0022"
down_revision: Union[str, None] = "0021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "player_transfers",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("player_id", sa.Uuid(as_uuid=True), sa.ForeignKey("players.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("vendor", sa.String(50), nullable=False),
        sa.Column("transfer_date", sa.Date, nullable=True),
        sa.Column("transfer_type", sa.String(50), nullable=True),
        sa.Column("team_in_vendor_id", sa.String(50), nullable=True),
        sa.Column("team_in_name", sa.String(200), nullable=True),
        sa.Column("team_in_crest_url", sa.String(512), nullable=True),
        sa.Column("team_out_vendor_id", sa.String(50), nullable=True),
        sa.Column("team_out_name", sa.String(200), nullable=True),
        sa.Column("team_out_crest_url", sa.String(512), nullable=True),
        sa.Column("fee_display", sa.String(100), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "player_injuries",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("player_id", sa.Uuid(as_uuid=True), sa.ForeignKey("players.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("vendor", sa.String(50), nullable=False),
        sa.Column("league_name", sa.String(200), nullable=True),
        sa.Column("season", sa.String(20), nullable=True),
        sa.Column("fixture_date", sa.Date, nullable=True, index=True),
        sa.Column("injury_type", sa.String(200), nullable=True),
        sa.Column("reason", sa.String(500), nullable=True),
        sa.Column("games_absent", sa.Integer, nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("player_injuries")
    op.drop_table("player_transfers")
