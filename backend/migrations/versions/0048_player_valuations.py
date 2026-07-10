"""TRA-91: player_valuations — append-only fair-value model history.

Revision ID: 0048
Revises: 0047
Create Date: 2026-07-06
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision: str = "0048"
down_revision: Union[str, None] = "0047"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE TYPE valuationconfidence AS ENUM ('HIGH', 'MEDIUM', 'LOW')")

    op.create_table(
        "player_valuations",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("player_id", sa.Uuid(as_uuid=True), sa.ForeignKey("players.id", ondelete="CASCADE"), nullable=False),
        sa.Column("fair_value", sa.Numeric(15, 2), nullable=False),
        sa.Column("fair_value_low", sa.Numeric(15, 2), nullable=False),
        sa.Column("fair_value_high", sa.Numeric(15, 2), nullable=False),
        sa.Column("currency", sa.String(10), nullable=False, server_default="GBP"),
        sa.Column("performance_score", sa.Numeric(5, 2), nullable=False),
        sa.Column("confidence", pg.ENUM("HIGH", "MEDIUM", "LOW", name="valuationconfidence", create_type=False), nullable=False),
        sa.Column("model_version", sa.String(50), nullable=False),
        sa.Column("league_tier", sa.Integer, nullable=False),
        sa.Column("age_factor", sa.Numeric(4, 2), nullable=False),
        sa.Column("inputs_json", pg.JSONB, nullable=True),
        sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index(
        "ix_player_valuations_player_id_computed_at",
        "player_valuations",
        ["player_id", "computed_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_player_valuations_player_id_computed_at", table_name="player_valuations")
    op.drop_table("player_valuations")
    op.execute("DROP TYPE valuationconfidence")
