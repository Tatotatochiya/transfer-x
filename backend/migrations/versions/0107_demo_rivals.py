"""Demo mode: whether rival house clubs bid against the tester

Revision ID: 0107
Revises: 0106
Create Date: 2026-11-03
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0107"
down_revision: Union[str, None] = "0106"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("demo_runs", sa.Column("rivals", sa.String(20), nullable=False, server_default="sometimes"))


def downgrade() -> None:
    op.drop_column("demo_runs", "rivals")
