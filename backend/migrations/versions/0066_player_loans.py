"""Player loans

Phase 2 of docs/feature_spec/loan-transfers.md.

A loan needs two simultaneous relationships — the parent owns, the loanee
registers — but `normalize_player_status` resolves the active contract with
`scalar_one_or_none()`, so two active contract rows raise MultipleResultsFound
rather than merely misbehaving. That invariant is preserved: the loanee holds
the one active contract and this table is what says who owns the player.

`parent_contract_id` points at the contract suspended when the loan started, so
the return is a restore of the agreement the parent already had rather than a
new one with a guessed wage and end date.

Revision ID: 0066
Revises: 0065
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0066"
down_revision: Union[str, None] = "0065"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create the type explicitly, then reference it with create_type=False:
    # create_table would otherwise try to emit CREATE TYPE a second time.
    loanstatus = postgresql.ENUM(
        "ACTIVE", "COMPLETED", "RECALLED", "CONVERTED", name="loanstatus"
    )
    loanstatus.create(op.get_bind(), checkfirst=True)
    loanstatus_col = postgresql.ENUM(
        "ACTIVE", "COMPLETED", "RECALLED", "CONVERTED",
        name="loanstatus",
        create_type=False,
    )

    op.create_table(
        "player_loans",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column(
            "player_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("players.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "deal_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("deals.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "parent_club_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("clubs.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "loanee_club_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("clubs.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "parent_contract_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("contracts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "loanee_contract_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("contracts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("loan_fee", sa.Numeric(15, 2), nullable=True),
        sa.Column("wage_split_pct", sa.Numeric(5, 4), nullable=True),
        sa.Column(
            "loanee_wage_share", sa.Numeric(15, 2), nullable=False, server_default="0"
        ),
        sa.Column("option_to_buy", sa.Numeric(15, 2), nullable=True),
        sa.Column(
            "obligation_to_buy", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column(
            "recall_allowed", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column("status", loanstatus_col, nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("end_reason", sa.String(30), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_player_loans_player_id", "player_loans", ["player_id"])
    op.create_index("ix_player_loans_deal_id", "player_loans", ["deal_id"])
    op.create_index("ix_player_loans_parent_club_id", "player_loans", ["parent_club_id"])
    op.create_index("ix_player_loans_loanee_club_id", "player_loans", ["loanee_club_id"])
    op.create_index("ix_player_loans_status", "player_loans", ["status"])
    # The expiry job (phase 3) scans on end_date among ACTIVE rows.
    op.create_index("ix_player_loans_end_date", "player_loans", ["end_date"])


def downgrade() -> None:
    op.drop_table("player_loans")
    sa.Enum(name="loanstatus").drop(op.get_bind(), checkfirst=True)
