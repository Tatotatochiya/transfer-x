"""TRA-127: AgentNegotiation table — three-way negotiation stage.

Revision ID: 0034
Revises: 0033
Create Date: 2026-06-20
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0034"
down_revision: Union[str, None] = "0033"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE TYPE negotiationstatus AS ENUM ('IN_PROGRESS', 'TERMS_AGREED', 'COLLAPSED')")
    op.execute("CREATE TYPE agreementstatus AS ENUM ('PENDING', 'AGREED', 'DECLINED')")
    op.execute("CREATE TYPE commissionpayer AS ENUM ('BUYER', 'SELLER', 'PLAYER')")

    op.create_table(
        "agent_negotiations",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column(
            "deal_id", sa.Uuid(as_uuid=True),
            sa.ForeignKey("deals.id", ondelete="CASCADE"),
            nullable=False, unique=True, index=True,
        ),
        sa.Column(
            "agent_id", sa.Uuid(as_uuid=True),
            sa.ForeignKey("agent_profiles.id", ondelete="CASCADE"),
            nullable=False, index=True,
        ),
        sa.Column(
            "status",
            sa.Enum("IN_PROGRESS", "TERMS_AGREED", "COLLAPSED", name="negotiationstatus"),
            nullable=False, server_default="IN_PROGRESS",
        ),
        # Club-side commission terms
        sa.Column("commission_pct", sa.Numeric(5, 4), nullable=True),
        sa.Column("commission_amount", sa.Numeric(15, 2), nullable=True),
        sa.Column(
            "commission_payer",
            sa.Enum("BUYER", "SELLER", "PLAYER", name="commissionpayer"),
            nullable=True,
        ),
        sa.Column("additional_conditions", sa.Text, nullable=True),
        sa.Column(
            "club_agreement",
            sa.Enum("PENDING", "AGREED", "DECLINED", name="agreementstatus"),
            nullable=False, server_default="PENDING",
        ),
        # Player-side personal terms
        sa.Column("proposed_wage_weekly", sa.Numeric(15, 2), nullable=True),
        sa.Column("proposed_signing_bonus", sa.Numeric(15, 2), nullable=True),
        sa.Column("proposed_length_years", sa.Integer, nullable=True),
        sa.Column(
            "player_agreement",
            sa.Enum("PENDING", "AGREED", "DECLINED", name="agreementstatus"),
            nullable=False, server_default="PENDING",
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.Column("agreed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("agent_negotiations")
    op.execute("DROP TYPE commissionpayer")
    op.execute("DROP TYPE agreementstatus")
    op.execute("DROP TYPE negotiationstatus")
