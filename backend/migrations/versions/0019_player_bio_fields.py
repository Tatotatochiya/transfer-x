"""Add bio fields to players (height, weight, birth, firstname, lastname).

Revision ID: 0019
Revises: 0018
Create Date: 2026-04-11
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0019"
down_revision: Union[str, None] = "0018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("players", sa.Column("firstname",     sa.String(100), nullable=True))
    op.add_column("players", sa.Column("lastname",      sa.String(100), nullable=True))
    op.add_column("players", sa.Column("height",        sa.String(20),  nullable=True))
    op.add_column("players", sa.Column("weight",        sa.String(20),  nullable=True))
    op.add_column("players", sa.Column("birth_date",    sa.Date(),      nullable=True))
    op.add_column("players", sa.Column("birth_place",   sa.String(200), nullable=True))
    op.add_column("players", sa.Column("birth_country", sa.String(100), nullable=True))


def downgrade() -> None:
    op.drop_column("players", "birth_country")
    op.drop_column("players", "birth_place")
    op.drop_column("players", "birth_date")
    op.drop_column("players", "weight")
    op.drop_column("players", "height")
    op.drop_column("players", "lastname")
    op.drop_column("players", "firstname")
