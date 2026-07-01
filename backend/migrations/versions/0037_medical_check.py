"""TRA-61: medical_checks table.

Revision ID: 0037
Revises: 0036
Create Date: 2026-06-20
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision: str = "0037"
down_revision: Union[str, None] = "0036"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE TYPE medicalstatus AS ENUM ('PENDING', 'PASSED', 'FAILED')")

    op.create_table(
        "medical_checks",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column(
            "deal_id", sa.Uuid(as_uuid=True),
            sa.ForeignKey("deals.id", ondelete="CASCADE"),
            nullable=False, unique=True, index=True,
        ),
        sa.Column(
            "status",
            pg.ENUM("PENDING", "PASSED", "FAILED", name="medicalstatus", create_type=False),
            nullable=False, server_default="PENDING",
        ),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("medical_checks")
    op.execute("DROP TYPE medicalstatus")
