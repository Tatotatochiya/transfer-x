"""Add client profile fields to mandates table.

Revision ID: 0028
Revises: 0027
Create Date: 2026-06-20
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0028"
down_revision: Union[str, None] = "0027"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "CREATE TYPE clientstatus AS ENUM "
        "('ACTIVE', 'SEEKING_MOVE', 'LOAN_AVAILABLE', 'CONTRACT_EXTENSION', 'UNAVAILABLE')"
    )
    op.add_column(
        "mandates",
        sa.Column(
            "client_status",
            sa.Enum(
                "ACTIVE", "SEEKING_MOVE", "LOAN_AVAILABLE", "CONTRACT_EXTENSION", "UNAVAILABLE",
                name="clientstatus",
            ),
            nullable=False,
            server_default="ACTIVE",
        ),
    )
    op.add_column("mandates", sa.Column("agent_notes", sa.Text(), nullable=True))
    op.add_column("mandates", sa.Column("preferred_destinations", sa.Text(), nullable=True))
    op.add_column("mandates", sa.Column("asking_price", sa.Numeric(15, 2), nullable=True))
    op.add_column("mandates", sa.Column("asking_wage", sa.Numeric(15, 2), nullable=True))


def downgrade() -> None:
    op.drop_column("mandates", "asking_wage")
    op.drop_column("mandates", "asking_price")
    op.drop_column("mandates", "preferred_destinations")
    op.drop_column("mandates", "agent_notes")
    op.drop_column("mandates", "client_status")
    op.execute("DROP TYPE IF EXISTS clientstatus")
