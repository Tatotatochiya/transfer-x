"""M8: add association column to transfer_windows for per-league window enforcement.

Existing rows with association=NULL are treated as global windows (apply to all clubs).

Revision ID: 0059
Revises: 0058
Create Date: 2026-07-12
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0059"
down_revision: Union[str, None] = "0058"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "transfer_windows",
        sa.Column("association", sa.String(100), nullable=True),
    )
    op.create_index("ix_transfer_windows_association", "transfer_windows", ["association"])


def downgrade() -> None:
    op.drop_index("ix_transfer_windows_association", table_name="transfer_windows")
    op.drop_column("transfer_windows", "association")
