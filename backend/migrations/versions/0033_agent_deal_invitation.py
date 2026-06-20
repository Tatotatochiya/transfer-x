"""TRA-125: AGENT_NEGOTIATION deal stage + AgentDealInvitation table.

Revision ID: 0033
Revises: 0032
Create Date: 2026-06-20
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0033"
down_revision: Union[str, None] = "0032"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE dealstage ADD VALUE IF NOT EXISTS 'AGENT_NEGOTIATION'")
    op.execute("ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'DEAL_AGENT_INVITED'")

    op.execute("CREATE TYPE invitationstatus AS ENUM ('PENDING', 'ACCEPTED', 'DECLINED')")

    op.create_table(
        "agent_deal_invitations",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column(
            "deal_id", sa.Uuid(as_uuid=True),
            sa.ForeignKey("deals.id", ondelete="CASCADE"),
            nullable=False, index=True,
        ),
        sa.Column(
            "agent_id", sa.Uuid(as_uuid=True),
            sa.ForeignKey("agent_profiles.id", ondelete="CASCADE"),
            nullable=False, index=True,
        ),
        sa.Column(
            "status",
            sa.Enum("PENDING", "ACCEPTED", "DECLINED", name="invitationstatus"),
            nullable=False, server_default="PENDING",
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("agent_deal_invitations")
    op.execute("DROP TYPE invitationstatus")
    # dealstage / notificationtype enum value removal is a no-op in Postgres.
