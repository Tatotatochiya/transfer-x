"""Mobile notifications (Web Push), phase 1

docs/feature_spec/mobile-notifications. `notifications` gains a push title
and body, the subject it is about (`group_key`, also the push tag), the
subject's deadline and up to two action links. `user_preferences` gains the
tier settings, quiet hours, the morning summary time, the user's timezone
and "hide amounts on the lock screen". `notification_preferences` gains a
per-type push switch. New tables hold each device's push subscription and
every push decision (`push_deliveries`: sent, held for quiet hours, skipped
as a repeat, failed).

Revision ID: 0088
Revises: 0087
Create Date: 2026-10-02
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0088"
down_revision: Union[str, None] = "0087"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PUSH_MODE = postgresql.ENUM("SOUND", "SILENT", "OFF", name="pushmode", create_type=False)
PUSH_PLATFORM = postgresql.ENUM("IOS_HOME_SCREEN", "ANDROID", "DESKTOP", "OTHER", name="pushplatform", create_type=False)
PUSH_STATUS = postgresql.ENUM(
    "SENT", "HELD", "SKIPPED_DUPLICATE", "SKIPPED", "FAILED", name="pushdeliverystatus", create_type=False,
)
NOTIFICATION_TYPE = postgresql.ENUM(name="notificationtype", create_type=False)


def upgrade() -> None:
    bind = op.get_bind()
    for enum in (PUSH_MODE, PUSH_PLATFORM, PUSH_STATUS):
        enum.create(bind, checkfirst=True)

    op.add_column("notifications", sa.Column("title", sa.String(120), nullable=True))
    op.add_column("notifications", sa.Column("body", sa.String(240), nullable=True))
    op.add_column("notifications", sa.Column("group_key", sa.String(120), nullable=True))
    op.add_column("notifications", sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("notifications", sa.Column("actions_json", postgresql.JSONB(), nullable=True))
    op.create_index("ix_notifications_group_key", "notifications", ["group_key"])
    # The scheduled reminders look up "already told this person about this
    # subject" by these three columns.
    op.create_index(
        "ix_notifications_recipient_type_group", "notifications", ["recipient_user_id", "type", "group_key"],
    )

    op.add_column("user_preferences", sa.Column("push_your_move", PUSH_MODE, nullable=False, server_default="SOUND"))
    op.add_column("user_preferences", sa.Column("push_heads_up", PUSH_MODE, nullable=False, server_default="SILENT"))
    op.add_column("user_preferences", sa.Column("push_summary", sa.Boolean(), nullable=False, server_default="true"))
    op.add_column("user_preferences", sa.Column("summary_local_time", sa.Time(), nullable=False, server_default="08:00"))
    op.add_column("user_preferences", sa.Column("quiet_hours_enabled", sa.Boolean(), nullable=False, server_default="true"))
    op.add_column("user_preferences", sa.Column("quiet_start", sa.Time(), nullable=False, server_default="22:00"))
    op.add_column("user_preferences", sa.Column("quiet_end", sa.Time(), nullable=False, server_default="07:00"))
    op.add_column("user_preferences", sa.Column("timezone", sa.String(64), nullable=False, server_default="Europe/London"))
    op.add_column("user_preferences", sa.Column("push_hide_amounts", sa.Boolean(), nullable=False, server_default="false"))

    op.add_column(
        "notification_preferences", sa.Column("push_enabled", sa.Boolean(), nullable=False, server_default="true"),
    )

    op.create_table(
        "push_subscriptions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("endpoint", sa.Text(), nullable=False, unique=True),
        sa.Column("p256dh", sa.String(200), nullable=False),
        sa.Column("auth", sa.String(200), nullable=False),
        sa.Column("platform", PUSH_PLATFORM, nullable=False, server_default="OTHER"),
        sa.Column("user_agent", sa.String(300), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_failure_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_count", sa.Integer(), nullable=False, server_default="0"),
    )

    op.create_table(
        "push_deliveries",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("notification_id", sa.Uuid(), sa.ForeignKey("notifications.id", ondelete="CASCADE"), nullable=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("type", NOTIFICATION_TYPE, nullable=True),
        sa.Column("group_key", sa.String(120), nullable=True),
        sa.Column("status", PUSH_STATUS, nullable=False),
        sa.Column("send_after", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_push_deliveries_dedupe", "push_deliveries", ["user_id", "type", "group_key", "sent_at"])
    op.create_index("ix_push_deliveries_held", "push_deliveries", ["status", "send_after"])


def downgrade() -> None:
    op.drop_index("ix_push_deliveries_held", table_name="push_deliveries")
    op.drop_index("ix_push_deliveries_dedupe", table_name="push_deliveries")
    op.drop_table("push_deliveries")
    op.drop_table("push_subscriptions")
    op.drop_column("notification_preferences", "push_enabled")
    for col in (
        "push_hide_amounts", "timezone", "quiet_end", "quiet_start", "quiet_hours_enabled",
        "summary_local_time", "push_summary", "push_heads_up", "push_your_move",
    ):
        op.drop_column("user_preferences", col)
    op.drop_index("ix_notifications_recipient_type_group", table_name="notifications")
    op.drop_index("ix_notifications_group_key", table_name="notifications")
    for col in ("actions_json", "deadline_at", "group_key", "body", "title"):
        op.drop_column("notifications", col)
    bind = op.get_bind()
    for enum in (PUSH_STATUS, PUSH_PLATFORM, PUSH_MODE):
        enum.drop(bind, checkfirst=True)
