"""Add last_actor_club_id to offers for turn-based negotiation.

Revision ID: 0015
Revises: 0014
Create Date: 2026-03-28
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0015"
down_revision: Union[str, None] = "0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "offers",
        sa.Column(
            "last_actor_club_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("clubs.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    # Backfill SENT offers: last actor is always the buyer (from_club_id)
    op.execute("""
        UPDATE offers
        SET last_actor_club_id = from_club_id
        WHERE status = 'SENT'
    """)

    # Backfill COUNTERED offers: last actor is the club on the most recent COUNTERED event
    op.execute("""
        UPDATE offers o
        SET last_actor_club_id = (
            SELECT oe.actor_club_id
            FROM offer_events oe
            WHERE oe.offer_id = o.id
              AND oe.event_type = 'COUNTERED'
            ORDER BY oe.created_at DESC
            LIMIT 1
        )
        WHERE o.status = 'COUNTERED'
    """)


def downgrade() -> None:
    op.drop_column("offers", "last_actor_club_id")
