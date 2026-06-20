"""TRA-66: Add valuation + contract/wage enrichment columns to players table.

Revision ID: 0032
Revises: 0031
Create Date: 2026-06-20
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0032"
down_revision: Union[str, None] = "0031"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE TYPE valuationsource AS ENUM ('ETV', 'TRANSFERMARKT', 'MANUAL')")
    op.execute("CREATE TYPE wagesource AS ENUM ('CAPOLOGY', 'ESTIMATED', 'MANUAL')")

    # Valuation
    op.add_column("players", sa.Column("market_value", sa.Numeric(15, 2), nullable=True))
    op.add_column("players", sa.Column("market_value_currency", sa.String(10), nullable=True))
    op.add_column("players", sa.Column("valuation_low", sa.Numeric(15, 2), nullable=True))
    op.add_column("players", sa.Column("valuation_high", sa.Numeric(15, 2), nullable=True))
    op.add_column("players", sa.Column(
        "valuation_source",
        sa.Enum("ETV", "TRANSFERMARKT", "MANUAL", name="valuationsource"),
        nullable=True,
    ))
    op.add_column("players", sa.Column("valuation_as_of", sa.Date(), nullable=True))

    # Contract / wages
    op.add_column("players", sa.Column("contract_expiry", sa.Date(), nullable=True))
    op.add_column("players", sa.Column("contract_signed", sa.Date(), nullable=True))
    op.add_column("players", sa.Column("wage_weekly", sa.Numeric(15, 2), nullable=True))
    op.add_column("players", sa.Column("wage_currency", sa.String(10), nullable=True))
    op.add_column("players", sa.Column(
        "wage_source",
        sa.Enum("CAPOLOGY", "ESTIMATED", "MANUAL", name="wagesource"),
        nullable=True,
    ))
    op.add_column("players", sa.Column(
        "wage_verified", sa.Boolean(), nullable=False, server_default="false"
    ))

    # External provider IDs (TRA-67 will use these for stable re-sync)
    op.add_column("players", sa.Column("etv_player_id", sa.String(100), nullable=True))
    op.add_column("players", sa.Column("capology_slug", sa.String(200), nullable=True))


def downgrade() -> None:
    for col in [
        "capology_slug", "etv_player_id", "wage_verified", "wage_source",
        "wage_currency", "wage_weekly", "contract_signed", "contract_expiry",
        "valuation_as_of", "valuation_source", "valuation_high", "valuation_low",
        "market_value_currency", "market_value",
    ]:
        op.drop_column("players", col)
    op.execute("DROP TYPE valuationsource")
    op.execute("DROP TYPE wagesource")
