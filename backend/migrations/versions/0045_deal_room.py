"""TRA-81: deal room — versioned terms, threaded comments, attachments.

Revision ID: 0045
Revises: 0044
Create Date: 2026-07-03
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0045"
down_revision: Union[str, None] = "0044"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "deal_terms_versions",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("deal_id", sa.Uuid(as_uuid=True), sa.ForeignKey("deals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_number", sa.Integer, nullable=False),
        sa.Column("terms_snapshot", sa.JSON, nullable=False),
        sa.Column(
            "changed_by_user_id", sa.Uuid(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_deal_terms_versions_deal_id", "deal_terms_versions", ["deal_id"])
    op.create_index("ix_deal_terms_versions_created_at", "deal_terms_versions", ["created_at"])

    op.create_table(
        "deal_comments",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("deal_id", sa.Uuid(as_uuid=True), sa.ForeignKey("deals.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "parent_id", sa.Uuid(as_uuid=True),
            sa.ForeignKey("deal_comments.id", ondelete="CASCADE"), nullable=True,
        ),
        sa.Column(
            "author_user_id", sa.Uuid(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("mentioned_user_ids", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_deal_comments_deal_id", "deal_comments", ["deal_id"])
    op.create_index("ix_deal_comments_parent_id", "deal_comments", ["parent_id"])
    op.create_index("ix_deal_comments_created_at", "deal_comments", ["created_at"])

    op.create_table(
        "deal_attachments",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("deal_id", sa.Uuid(as_uuid=True), sa.ForeignKey("deals.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "uploaded_by_user_id", sa.Uuid(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("size_bytes", sa.Integer, nullable=False),
        sa.Column("storage_path", sa.String(500), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_deal_attachments_deal_id", "deal_attachments", ["deal_id"])
    op.create_index("ix_deal_attachments_created_at", "deal_attachments", ["created_at"])


def downgrade() -> None:
    op.drop_table("deal_attachments")
    op.drop_table("deal_comments")
    op.drop_table("deal_terms_versions")
