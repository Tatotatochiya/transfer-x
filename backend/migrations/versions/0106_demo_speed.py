"""Demo mode: how fast house clubs answer in a run

Revision ID: 0106
Revises: 0105
Create Date: 2026-11-02
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0106"
down_revision: Union[str, None] = "0105"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("demo_runs", sa.Column("speed", sa.String(20), nullable=False, server_default="instant"))


def downgrade() -> None:
    op.drop_column("demo_runs", "speed")
