"""Signed terms behind a consent recorded by the buying club

personal_terms.consent_evidence_attachment_id: when the buying club records
the answer for a player with no account or agent (product ADR 0006), the
deal-room document holding the signed terms.

Revision ID: 0081
Revises: 0080
Create Date: 2026-09-28
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0081"
down_revision: Union[str, None] = "0080"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "personal_terms",
        sa.Column("consent_evidence_attachment_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_personal_terms_consent_evidence",
        "personal_terms", "deal_attachments",
        ["consent_evidence_attachment_id"], ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_personal_terms_consent_evidence", "personal_terms", type_="foreignkey")
    op.drop_column("personal_terms", "consent_evidence_attachment_id")
