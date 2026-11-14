"""Counters on the agent's commission and on personal terms: whose terms are on
the table, and every round (docs/product/decisions/0012-commission-and-personal-terms-are-negotiated.md).

Revision ID: 0113
Revises: 0112
Create Date: 2026-11-14
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0113"
down_revision: Union[str, None] = "0112"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("agent_negotiations", sa.Column("proposed_by", sa.String(10), nullable=True))
    op.add_column("personal_terms", sa.Column("proposed_by", sa.String(10), nullable=True))
    op.create_table(
        "term_proposals",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("deal_id", sa.Uuid(as_uuid=True), sa.ForeignKey("deals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("side", sa.String(10), nullable=False),
        sa.Column("terms", sa.JSON(), nullable=False),
        sa.Column("note", sa.String(200), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_term_proposals_deal_id", "term_proposals", ["deal_id"])


def downgrade() -> None:
    op.drop_index("ix_term_proposals_deal_id", table_name="term_proposals")
    op.drop_table("term_proposals")
    op.drop_column("personal_terms", "proposed_by")
    op.drop_column("agent_negotiations", "proposed_by")
