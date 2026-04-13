"""merge_stats_full_and_nullable_created_by

Revision ID: 17e5dc6d7ccc
Revises: 0008, c1aef17f0fb1
Create Date: 2026-03-21 13:50:04.021868

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '17e5dc6d7ccc'
down_revision: Union[str, None] = ('0008', 'c1aef17f0fb1')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
