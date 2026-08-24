"""Loan terms on offers, and wage reservation

Phase 1 of docs/feature_spec/loan-transfers.md.

An offer had no type discriminator, so a loan could only be negotiated as if it
were permanent and then retyped in the deal room *after* the seller had already
accepted it. `deal_type` and the loan terms move onto the offer so a loan is a
loan from the first approach.

`reserved_wage_weekly` is the other half of a bug that predates loans entirely:
`reserve_budget` has always accepted a `wage_weekly` argument with a real
affordability check behind it, and no offer path has ever passed one. Reserving
wage is only safe if we also record how much was reserved, or withdrawing an
offer cannot release the right amount.

Existing rows backfill to PERMANENT with a null wage reservation, which is what
every offer made before this was. Nothing recomputes historic reservations —
those clubs' committed totals are already settled and rewriting them would move
money that was never held.

Revision ID: 0065
Revises: 0064
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0065"
down_revision: Union[str, None] = "0064"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # `dealtype` already exists (created with the deals table, TRA-56) — reuse it
    # rather than minting a second enum with the same members.
    dealtype = sa.Enum(
        "PERMANENT", "LOAN", "FREE_TRANSFER", "PRE_CONTRACT",
        name="dealtype",
        create_type=False,
    )

    op.add_column(
        "offers",
        sa.Column("deal_type", dealtype, nullable=False, server_default="PERMANENT"),
    )
    op.add_column("offers", sa.Column("loan_start", sa.Date(), nullable=True))
    op.add_column("offers", sa.Column("loan_end", sa.Date(), nullable=True))
    op.add_column("offers", sa.Column("loan_fee", sa.Numeric(15, 2), nullable=True))
    op.add_column("offers", sa.Column("wage_split_pct", sa.Numeric(5, 4), nullable=True))
    op.add_column("offers", sa.Column("option_to_buy", sa.Numeric(15, 2), nullable=True))
    op.add_column(
        "offers",
        sa.Column("obligation_to_buy", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "offers",
        sa.Column("recall_allowed", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "offers",
        sa.Column(
            "reserved_wage_weekly",
            sa.Numeric(15, 2),
            nullable=False,
            server_default="0",
        ),
    )

    op.add_column("deals", sa.Column("wage_split_pct", sa.Numeric(5, 4), nullable=True))
    op.add_column(
        "deals",
        sa.Column("recall_allowed", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("deals", "recall_allowed")
    op.drop_column("deals", "wage_split_pct")
    op.drop_column("offers", "reserved_wage_weekly")
    op.drop_column("offers", "recall_allowed")
    op.drop_column("offers", "obligation_to_buy")
    op.drop_column("offers", "option_to_buy")
    op.drop_column("offers", "wage_split_pct")
    op.drop_column("offers", "loan_fee")
    op.drop_column("offers", "loan_end")
    op.drop_column("offers", "loan_start")
    op.drop_column("offers", "deal_type")
    # `dealtype` is not dropped — the deals table still uses it.
