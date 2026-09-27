""""Open to offers" means "listed"

A club had two ways to say a player was available — the squad's "open to
offers" switch and a public listing — and they could disagree (a player page
reading "Closed to offers" beside "View listing"). They are one concept now: a
player at a club is available when he is listed. `players.open_to_offers` is
kept, since the market filter, badges, scouting and AI search read it, but
only the listing lifecycle writes it (sales/service.sync_listed_flag).

This aligns existing rows: for every player registered to a club, the flag
becomes whether he has an open listing. Free agents keep their value — no club
lists them, so the flag stays theirs to set. Not reversible: the old switch
values are not recoverable, and restoring them would reintroduce the
disagreement.

Revision ID: 0078
Revises: 0077
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0078"
down_revision: Union[str, None] = "0077"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE players SET open_to_offers = EXISTS (
            SELECT 1 FROM sales
            WHERE sales.player_id = players.id AND sales.status = 'OPEN'
        )
        WHERE current_club_id IS NOT NULL
        """
    )


def downgrade() -> None:
    # The previous switch values are gone; nothing to restore.
    pass
