"""Player invitations from an agent or TransferX staff, for free agents

A free agent has no club to invite him. His mandated agent or TransferX staff
can instead: player_invitations.club_id becomes nullable, and agent_id records
an agent's invitation (both null: sent by staff; invited_by_user_id says who).

Revision ID: 0083
Revises: 0082
Create Date: 2026-09-28
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0083"
down_revision: Union[str, None] = "0082"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("player_invitations", "club_id", existing_type=sa.Uuid(), nullable=True)
    op.add_column("player_invitations", sa.Column("agent_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_player_invitations_agent", "player_invitations", "agent_profiles",
        ["agent_id"], ["id"], ondelete="CASCADE",
    )
    op.create_index("ix_player_invitations_agent_id", "player_invitations", ["agent_id"])


def downgrade() -> None:
    op.drop_index("ix_player_invitations_agent_id", table_name="player_invitations")
    op.drop_constraint("fk_player_invitations_agent", "player_invitations", type_="foreignkey")
    op.drop_column("player_invitations", "agent_id")
    # Invitations sent by an agent or staff have no club; they cannot survive
    # the column becoming required again.
    op.execute("DELETE FROM player_invitations WHERE club_id IS NULL")
    op.alter_column("player_invitations", "club_id", existing_type=sa.Uuid(), nullable=False)
