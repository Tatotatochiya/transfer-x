"""make_player_created_by_nullable

Revision ID: c1aef17f0fb1
Revises: 0007
Create Date: 2026-03-17 23:41:16.833641

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'c1aef17f0fb1'
down_revision: Union[str, None] = '0007'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('players', 'created_by_user_id',
                    existing_type=postgresql.UUID(),
                    nullable=True)


def downgrade() -> None:
    op.alter_column('players', 'created_by_user_id',
                    existing_type=postgresql.UUID(),
                    nullable=False)
