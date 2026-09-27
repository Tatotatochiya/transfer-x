"""Deal structure on the offer; the consented contract on the deal

Two gaps between what was agreed and what was executed.

1. An offer could carry only a fee, a wage and a contract length. The payment
   schedule, add-on clauses and sell-on — the terms that decide what a deal is
   worth — could only be added in the deal room after the seller had accepted,
   by either club alone. They are now agreed on the offer (`instalments`,
   `clauses`, `sell_on_pct`) and copied onto the deal at acceptance.

2. The player consents to a wage, signing bonus and contract length at
   PERSONAL_TERMS, but completion built his contract from the offer's opening
   wage with no end date and no bonus. The consented figures are now carried
   onto the deal (`agreed_wage_weekly` already exists; `signing_bonus` and
   `contract_length_years` are new) and used at completion.

Revision ID: 0075
Revises: 0074
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0075"
down_revision: Union[str, None] = "0074"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("offers", sa.Column("instalments", sa.JSON(), nullable=False, server_default="[]"))
    op.add_column("offers", sa.Column("clauses", sa.JSON(), nullable=False, server_default="[]"))
    op.add_column("offers", sa.Column("sell_on_pct", sa.Numeric(5, 4), nullable=True))
    op.add_column("deals", sa.Column("signing_bonus", sa.Numeric(15, 2), nullable=True))
    op.add_column("deals", sa.Column("contract_length_years", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("deals", "contract_length_years")
    op.drop_column("deals", "signing_bonus")
    op.drop_column("offers", "sell_on_pct")
    op.drop_column("offers", "clauses")
    op.drop_column("offers", "instalments")
