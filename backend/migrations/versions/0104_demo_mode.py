"""Demo mode: demo runs, their change journal, house clubs and testers

Revision ID: 0104
Revises: 0103
Create Date: 2026-10-27
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0104"
down_revision: Union[str, None] = "0103"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "demo_runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("club_id", sa.Uuid(), sa.ForeignKey("clubs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="ACTIVE"),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("report", sa.JSON(), nullable=True),
    )
    op.create_index("ix_demo_runs_user_id", "demo_runs", ["user_id"])
    op.create_index("ix_demo_runs_status", "demo_runs", ["status"])
    op.create_table(
        "demo_changes",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.Uuid(), sa.ForeignKey("demo_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("table_name", sa.String(64), nullable=False),
        sa.Column("pk", sa.Text(), nullable=False),
        sa.Column("op", sa.String(10), nullable=False),
        sa.Column("before", sa.JSON(), nullable=True),
        sa.Column("after", sa.JSON(), nullable=True),
        sa.Column("at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_demo_changes_run_id", "demo_changes", ["run_id"])
    # The journal looks rows up by table and key ("did a demo insert this?").
    op.create_index("ix_demo_changes_table_pk", "demo_changes", ["table_name", "pk"])
    op.add_column("clubs", sa.Column("house_club", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("clubs", sa.Column("house_personality", sa.String(20), nullable=True))
    op.add_column("users", sa.Column("can_demo", sa.Boolean(), nullable=False, server_default="false"))


def downgrade() -> None:
    op.drop_column("users", "can_demo")
    op.drop_column("clubs", "house_personality")
    op.drop_column("clubs", "house_club")
    op.drop_index("ix_demo_changes_table_pk", table_name="demo_changes")
    op.drop_index("ix_demo_changes_run_id", table_name="demo_changes")
    op.drop_table("demo_changes")
    op.drop_index("ix_demo_runs_status", table_name="demo_runs")
    op.drop_index("ix_demo_runs_user_id", table_name="demo_runs")
    op.drop_table("demo_runs")
