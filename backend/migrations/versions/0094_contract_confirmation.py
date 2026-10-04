"""Check your squad: when a club confirmed each contract, and who

Revision ID: 0094
Revises: 0093
Create Date: 2026-10-04
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0094"
down_revision: Union[str, None] = "0093"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("contracts", sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("contracts", sa.Column("confirmed_by_user_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_contracts_confirmed_by_user_id", "contracts", "users", ["confirmed_by_user_id"], ["id"], ondelete="SET NULL"
    )


def downgrade() -> None:
    op.drop_constraint("fk_contracts_confirmed_by_user_id", "contracts", type_="foreignkey")
    op.drop_column("contracts", "confirmed_by_user_id")
    op.drop_column("contracts", "confirmed_at")
