"""Add extra stat fields to player_stats.

Revision ID: 0021
Revises: 0020
Create Date: 2026-04-12
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0021"
down_revision: Union[str, None] = "0020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("player_stats", sa.Column("penalty_won", sa.Integer, nullable=True))
    op.add_column("player_stats", sa.Column("penalty_committed", sa.Integer, nullable=True))
    op.add_column("player_stats", sa.Column("penalty_saved", sa.Integer, nullable=True))
    op.add_column("player_stats", sa.Column("cards_yellowred", sa.Integer, nullable=True))
    op.add_column("player_stats", sa.Column("substitutes_in", sa.Integer, nullable=True))
    op.add_column("player_stats", sa.Column("substitutes_out", sa.Integer, nullable=True))
    op.add_column("player_stats", sa.Column("substitutes_bench", sa.Integer, nullable=True))
    op.add_column("player_stats", sa.Column("passes_total", sa.Integer, nullable=True))
    op.add_column("player_stats", sa.Column("dribbles_past", sa.Integer, nullable=True))
    op.add_column("player_stats", sa.Column("position_played", sa.String(10), nullable=True))


def downgrade() -> None:
    for col in [
        "penalty_won", "penalty_committed", "penalty_saved", "cards_yellowred",
        "substitutes_in", "substitutes_out", "substitutes_bench",
        "passes_total", "dribbles_past", "position_played",
    ]:
        op.drop_column("player_stats", col)
