"""TRA-60: PERSONAL_TERMS deal stage + personal_terms table.

Revision ID: 0035
Revises: 0034
Create Date: 2026-06-20
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0035"
down_revision: Union[str, None] = "0034"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE dealstage ADD VALUE IF NOT EXISTS 'PERSONAL_TERMS'")
    op.execute("ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'DEAL_PERSONAL_TERMS_SENT'")

    op.create_table(
        "personal_terms",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column(
            "deal_id", sa.Uuid(as_uuid=True),
            sa.ForeignKey("deals.id", ondelete="CASCADE"),
            nullable=False, unique=True, index=True,
        ),
        sa.Column(
            "agent_id", sa.Uuid(as_uuid=True),
            sa.ForeignKey("agent_profiles.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("wage_weekly", sa.Numeric(15, 2), nullable=True),
        sa.Column("signing_bonus", sa.Numeric(15, 2), nullable=True),
        sa.Column("length_years", sa.Integer, nullable=True),
        sa.Column(
            "player_consent",
            sa.Enum("PENDING", "AGREED", "DECLINED", name="agreementstatus"),
            nullable=False, server_default="PENDING",
        ),
        sa.Column("agreed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("personal_terms")
    # dealstage / notificationtype enum value removal is a no-op in Postgres.
