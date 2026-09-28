"""Player invitations — players join TransferX by invitation from their club

A player account can accept personal terms, so it is no longer self-claimed
by player id. The owning club invites the player by email; accepting creates
the PLAYER user and links it to the player record. Same token discipline as
club and staff invitations (sha256 hash stored, raw token shown once).

Revision ID: 0082
Revises: 0081
Create Date: 2026-09-28
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0082"
down_revision: Union[str, None] = "0081"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "player_invitations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("player_id", sa.Uuid(), sa.ForeignKey("players.id", ondelete="CASCADE"), nullable=False),
        sa.Column("club_id", sa.Uuid(), sa.ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("invited_by_user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_player_invitations_player_id", "player_invitations", ["player_id"])
    op.create_index("ix_player_invitations_club_id", "player_invitations", ["club_id"])
    op.create_index("ix_player_invitations_email", "player_invitations", ["email"])
    op.create_index("ix_player_invitations_token_hash", "player_invitations", ["token_hash"], unique=True)


def downgrade() -> None:
    op.drop_table("player_invitations")
