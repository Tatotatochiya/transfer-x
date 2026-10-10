"""Scheduled data refresh and monitoring: job runs and their logs, grouped
errors, per-minute request figures

Revision ID: 0100
Revises: 0099
Create Date: 2026-10-10
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0100"
down_revision: Union[str, None] = "0099"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

BIGID = sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def upgrade() -> None:
    op.create_table(
        "job_runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("job", sa.String(100), nullable=False, index=True),
        sa.Column("parent_id", sa.Uuid(), sa.ForeignKey("job_runs.id", ondelete="CASCADE"), nullable=True, index=True),
        sa.Column("trigger", sa.String(20), nullable=False),
        sa.Column("service", sa.String(20), nullable=False),
        sa.Column("triggered_by_user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, index=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("summary", sa.JSON(), nullable=True),
        sa.Column("error", sa.String(2000), nullable=True),
    )
    op.create_table(
        "job_run_logs",
        sa.Column("id", BIGID, primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.Uuid(), sa.ForeignKey("job_runs.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("level", sa.String(10), nullable=False),
        sa.Column("logger", sa.String(120), nullable=False),
        sa.Column("message", sa.String(2000), nullable=False),
    )
    op.create_table(
        "error_issues",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("fingerprint", sa.String(64), nullable=False, unique=True),
        sa.Column("service", sa.String(20), nullable=False, index=True),
        sa.Column("level", sa.String(10), nullable=False),
        sa.Column("logger", sa.String(120), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("status", sa.String(10), nullable=False, server_default="open", index=True),
        sa.Column("first_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("hourly", sa.JSON(), nullable=True),
    )
    op.create_table(
        "error_events",
        sa.Column("id", BIGID, primary_key=True, autoincrement=True),
        sa.Column("issue_id", sa.Uuid(), sa.ForeignKey("error_issues.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("level", sa.String(10), nullable=False),
        sa.Column("message", sa.String(2000), nullable=False),
        sa.Column("traceback", sa.Text(), nullable=True),
        sa.Column("context", sa.JSON(), nullable=True),
    )
    op.create_table(
        "request_minutes",
        sa.Column("id", BIGID, primary_key=True, autoincrement=True),
        sa.Column("minute", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("method", sa.String(10), nullable=False),
        sa.Column("route", sa.String(200), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column("errors", sa.Integer(), nullable=False),
        sa.Column("p50_ms", sa.Integer(), nullable=False),
        sa.Column("p95_ms", sa.Integer(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("request_minutes")
    op.drop_table("error_events")
    op.drop_table("error_issues")
    op.drop_table("job_run_logs")
    op.drop_table("job_runs")
