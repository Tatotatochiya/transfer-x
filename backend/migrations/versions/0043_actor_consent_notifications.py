"""TRA-76: notification types for representation/consent/instalment/clause events.

Revision ID: 0043
Revises: 0042
Create Date: 2026-07-03
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0043"
down_revision: Union[str, None] = "0042"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NEW_VALUES = [
    "REPRESENTATION_STARTED",
    "REPRESENTATION_REVOKED",
    "PERSONAL_TERMS_DECISION",
    "INSTALMENT_DUE",
    "DEAL_CLAUSE_TRIGGERED",
]


def upgrade() -> None:
    for value in _NEW_VALUES:
        op.execute(f"ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS '{value}'")


def downgrade() -> None:
    # notificationtype enum value removal is a no-op in Postgres.
    pass
