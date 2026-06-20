"""TRA-63: hash refresh tokens at rest.

All existing raw-token rows are deleted on deploy — tokens issued before
this migration are invalidated (users will be asked to log in again).
No schema change needed: String(64) already fits a SHA-256 hex digest.

Revision ID: 0038
Revises: 0037
Create Date: 2026-06-20
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0038"
down_revision: Union[str, None] = "0037"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Invalidate all existing tokens (raw strings, not hashes).
    # Users will be prompted to log in again after this migration.
    op.execute("DELETE FROM refresh_tokens")


def downgrade() -> None:
    # Cannot unhash stored tokens; downgrade is intentionally a no-op.
    pass
