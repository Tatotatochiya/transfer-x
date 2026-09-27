"""Club invitations — clubs join by invitation only

Public sign-up let anyone claim to be any club (audit C3). Clubs now join by
invitation: TransferX staff invite a club's owner by email, and accepting the
invitation creates the account, the club and its finance record. Public club
registration is off unless `ALLOW_CLUB_SELF_REGISTRATION` is set (the test
suite sets it; real environments leave it off).

Revision ID: 0079
Revises: 0078
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0079"
down_revision: Union[str, None] = "0078"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "club_invitations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("email", sa.String(254), nullable=False, index=True),
        sa.Column("club_name", sa.String(200), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True, index=True),
        sa.Column("invited_by_user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("club_id", sa.Uuid(), sa.ForeignKey("clubs.id", ondelete="SET NULL"), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("club_invitations")
