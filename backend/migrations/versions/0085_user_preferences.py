"""User preferences — Lite mode and text size

Lite mode (docs/feature_spec/lite-mode) is a preference that follows the user
across devices. `lite_mode` null means the role default applies (off until
Lite's action cards ship). `text_scale` applies inside Lite only.
`lite_resume_json` holds the last unfinished Lite flow (used from L2).

Revision ID: 0085
Revises: 0084
Create Date: 2026-09-29
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0085"
down_revision: Union[str, None] = "0084"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TEXT_SCALE = postgresql.ENUM("NORMAL", "LARGE", "LARGER", name="textscale", create_type=False)


def upgrade() -> None:
    TEXT_SCALE.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "user_preferences",
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("lite_mode", sa.Boolean(), nullable=True),
        sa.Column("text_scale", TEXT_SCALE, nullable=False, server_default="NORMAL"),
        sa.Column("lite_resume_json", postgresql.JSONB(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("user_preferences")
    TEXT_SCALE.drop(op.get_bind(), checkfirst=True)
