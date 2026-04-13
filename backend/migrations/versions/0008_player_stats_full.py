"""Expand player_stats with full API-Football fields.

Revision ID: 0008
Revises: 0007
Create Date: 2026-03-21
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NEW_COLUMNS = [
    # Team context
    ("team_vendor_id", sa.String(50)),
    ("team_name",      sa.String(200)),
    # Games detail
    ("lineups",        sa.Integer()),
    ("shirt_number",   sa.Integer()),
    # Shots
    ("shots_total",    sa.Integer()),
    ("shots_on_target", sa.Integer()),
    # Passing
    ("key_passes",     sa.Integer()),
    ("pass_accuracy",  sa.Integer()),
    # Defending
    ("tackles_total",  sa.Integer()),
    ("interceptions",  sa.Integer()),
    ("blocks",         sa.Integer()),
    # Duels
    ("duels_total",    sa.Integer()),
    ("duels_won",      sa.Integer()),
    # Dribbles
    ("dribbles_attempts", sa.Integer()),
    ("dribbles_success",  sa.Integer()),
    # Discipline
    ("yellow_cards",      sa.Integer()),
    ("red_cards",         sa.Integer()),
    ("fouls_committed",   sa.Integer()),
    ("fouls_drawn",       sa.Integer()),
    # Goalkeeper specific
    ("saves",             sa.Integer()),
    ("goals_conceded",    sa.Integer()),
    # Penalty
    ("penalty_scored",    sa.Integer()),
    ("penalty_missed",    sa.Integer()),
]


def upgrade() -> None:
    for col_name, col_type in NEW_COLUMNS:
        op.add_column("player_stats", sa.Column(col_name, col_type, nullable=True))


def downgrade() -> None:
    for col_name, _ in reversed(NEW_COLUMNS):
        op.drop_column("player_stats", col_name)
