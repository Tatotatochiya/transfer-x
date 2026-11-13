"""Staff-entered transfer fees on player_transfers

Lets TransferX staff add or correct a transfer fee by hand, with the source
they took it from. Manual rows live beside the API-Football cache in the same
table (vendor = 'manual') and will survive the vendor sync once the code that
reads these columns is deployed. Additive and nullable, so it is safe to deploy
ahead of the code.

Revision ID: 0112
Revises: 0111
Create Date: 2026-11-13
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0112"
down_revision: Union[str, None] = "0111"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("player_transfers", sa.Column("fee_basis", sa.String(20), nullable=True))
    op.add_column("player_transfers", sa.Column("source_note", sa.String(500), nullable=True))
    op.add_column("player_transfers", sa.Column("source_url", sa.String(512), nullable=True))
    op.add_column("player_transfers", sa.Column("entered_by_user_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_player_transfers_entered_by",
        "player_transfers",
        "users",
        ["entered_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_player_transfers_entered_by", "player_transfers", type_="foreignkey"
    )
    op.drop_column("player_transfers", "entered_by_user_id")
    op.drop_column("player_transfers", "source_url")
    op.drop_column("player_transfers", "source_note")
    op.drop_column("player_transfers", "fee_basis")
