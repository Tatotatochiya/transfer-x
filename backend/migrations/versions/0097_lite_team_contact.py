"""Lite L7: the club's team contact, and the LITE_QUESTION notification

Revision ID: 0097
Revises: 0096
Create Date: 2026-10-04
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0097"
down_revision: Union[str, None] = "0096"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'LITE_QUESTION'")
    op.add_column("club_staff", sa.Column("is_lite_contact", sa.Boolean(), nullable=False, server_default="false"))


def downgrade() -> None:
    # Postgres can't drop an enum value; LITE_QUESTION stays.
    op.drop_column("club_staff", "is_lite_contact")
