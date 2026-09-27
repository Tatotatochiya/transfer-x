"""Club-run paperwork

Every deal stopped at PAPERWORK until TransferX staff moved it on, and only
staff could record the medical — platform staff sat in the path of every
transfer. The clubs now complete a checklist: each signs the transfer
agreement, and the buying club records the medical and confirms the
registration was submitted. The last step moves the deal to CONFIRMED. Staff
keep an override.

- `deals.agreement_signed_by_buyer_at`, `deals.agreement_signed_by_seller_at`,
  `deals.registration_submitted_at` (the medical already has its own table).
- `DEAL_PAPERWORK` notification type, for telling the other club a step is
  done and both when the paperwork is complete. As in 0067, the enum value
  cannot be removed on downgrade.

Revision ID: 0077
Revises: 0076
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0077"
down_revision: Union[str, None] = "0076"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'DEAL_PAPERWORK'")
    for column in (
        "agreement_signed_by_buyer_at",
        "agreement_signed_by_seller_at",
        "registration_submitted_at",
    ):
        op.add_column("deals", sa.Column(column, sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    for column in (
        "registration_submitted_at",
        "agreement_signed_by_seller_at",
        "agreement_signed_by_buyer_at",
    ):
        op.drop_column("deals", column)
    # Postgres cannot remove an enum value; DEAL_PAPERWORK is left in place.
