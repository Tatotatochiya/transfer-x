"""Daily "waiting on you" digest

Clubs use TransferX a few times a week, and in-app notifications alone let a
seven-day offer expire unseen. A daily email lists what is waiting on each
person (the dashboard's tier-1 list), sent once a day and only when there is
something.

- `DAILY_DIGEST` notification type, so the digest has an on/off switch on the
  notification preferences page like every other email. No in-app
  notification is ever created with it.
- `users.last_digest_sent_at`, which keeps it to one a day across restarts:
  the scheduler re-runs its jobs shortly after every start.

As in 0067, `ADD VALUE` cannot be reversed, so the downgrade leaves the enum
value in place.

Revision ID: 0076
Revises: 0075
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0076"
down_revision: Union[str, None] = "0075"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'DAILY_DIGEST'")
    op.add_column("users", sa.Column("last_digest_sent_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "last_digest_sent_at")
    # Postgres cannot remove an enum value; DAILY_DIGEST is left in place.
