"""Consolidate personal-terms capture into PersonalTerms only: drop the
player-side columns from agent_negotiations — AGENT_NEGOTIATION now
negotiates commission with the club exclusively, and personal terms are
proposed and consented to exactly once, at the PERSONAL_TERMS stage.

Revision ID: 0047
Revises: 0046
Create Date: 2026-07-04
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0047"
down_revision: Union[str, None] = "0046"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("agent_negotiations", "proposed_wage_weekly")
    op.drop_column("agent_negotiations", "proposed_signing_bonus")
    op.drop_column("agent_negotiations", "proposed_length_years")
    op.drop_column("agent_negotiations", "player_agreement")


def downgrade() -> None:
    import sqlalchemy as sa
    from sqlalchemy.dialects import postgresql as pg

    op.add_column(
        "agent_negotiations",
        sa.Column(
            "player_agreement",
            pg.ENUM("PENDING", "AGREED", "DECLINED", name="agreementstatus", create_type=False),
            nullable=False,
            server_default="PENDING",
        ),
    )
    op.add_column("agent_negotiations", sa.Column("proposed_length_years", sa.Integer(), nullable=True))
    op.add_column("agent_negotiations", sa.Column("proposed_signing_bonus", sa.Numeric(15, 2), nullable=True))
    op.add_column("agent_negotiations", sa.Column("proposed_wage_weekly", sa.Numeric(15, 2), nullable=True))
