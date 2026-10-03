"""Mobile notifications, phase 4: the email fallback

For "your move" notifications, someone with a phone subscription gets the
push first and the email only if the notification is still unread 30
minutes later. `email_due_at` is when that email is due; `emailed_at`, when
it went (or was dropped because the notification was read).

Revision ID: 0091
Revises: 0090
Create Date: 2026-10-03
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0091"
down_revision: Union[str, None] = "0090"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("notifications", sa.Column("email_due_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("notifications", sa.Column("emailed_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_notifications_email_due_at", "notifications", ["email_due_at"])


def downgrade() -> None:
    op.drop_index("ix_notifications_email_due_at", table_name="notifications")
    op.drop_column("notifications", "emailed_at")
    op.drop_column("notifications", "email_due_at")
