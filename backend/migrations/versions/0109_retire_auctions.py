"""Retire auctions

Auctions are no longer offered (product ADR 0011): a club lists a player open
to offers, with a date it will hear offers until if it wants one, and chooses
among the offers. Past auctions, bids and the deals they produced stay as
history. What was still live is wound down here:

- an auction still open becomes open to offers, keeping its deadline;
- every active bid is turned down and the budget it held is given back to
  the bidding club;
- a bid or a bid acceptance waiting for approval is cancelled.

Bidders aren't notified from here; a migration can't reach their phones.

Revision ID: 0109
Revises: 0108
Create Date: 2026-11-08
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0109"
down_revision: Union[str, None] = "0108"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Give back what each club's active bids held, then turn the bids down.
    op.execute("""
        UPDATE club_finances AS f
        SET transfer_reserved = GREATEST(f.transfer_reserved - b.transfer, 0),
            wage_reserved_weekly = GREATEST(f.wage_reserved_weekly - b.wage, 0)
        FROM (
            SELECT buyer_club_id,
                   SUM(COALESCE(reserved_transfer_amount, 0)) AS transfer,
                   SUM(COALESCE(reserved_wage_weekly, 0)) AS wage
            FROM bids WHERE status = 'ACTIVE' GROUP BY buyer_club_id
        ) AS b
        WHERE f.club_id = b.buyer_club_id
    """)
    op.execute("UPDATE bids SET status = 'REJECTED' WHERE status = 'ACTIVE'")
    op.execute("""
        UPDATE sales SET sale_type = 'OPEN_TO_OFFERS'
        WHERE sale_type = 'AUCTION' AND status = 'OPEN'
    """)
    op.execute("""
        UPDATE pending_approvals
        SET status = 'CANCELLED', decided_at = now(),
            failure_reason = 'Auctions are no longer offered'
        WHERE status = 'PENDING' AND action_type IN ('PLACE_BID', 'ACCEPT_BID')
    """)


def downgrade() -> None:
    # Winding down can't be undone: the bids' budget has been given back.
    pass
