"""Add EXTERNAL to playerstatus and reclassify vendor-imported players.

Players imported from the stats vendor were created FREE_AGENT because the enum
had no way to say "contracted, but to a club that isn't on TransferX". That made
~7.8k contracted professionals look like free agents — and, because
sign_free_agent gates solely on status == FREE_AGENT, signable for zero fee with
no selling club. See ADR 0003.

Backfill rule (same as players_service.normalize_player_status): a player with no
active TransferX contract but with a real-world club signal (team_name or
world_team_id) becomes EXTERNAL. Genuinely unattached players stay FREE_AGENT.
CONTRACTED rows are never touched.

Revision ID: 0063
Revises: 0062
Create Date: 2026-08-11
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0063"
down_revision: Union[str, None] = "0062"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    # Postgres needs the enum value added before any row can use it. ALTER TYPE
    # ... ADD VALUE cannot run inside a transaction block on older servers, so
    # commit the DDL separately. SQLite (test suite) stores enums as VARCHAR and
    # needs neither step.
    if bind.dialect.name == "postgresql":
        op.execute("COMMIT")
        op.execute("ALTER TYPE playerstatus ADD VALUE IF NOT EXISTS 'EXTERNAL'")

    op.execute(
        """
        UPDATE players
           SET status = 'EXTERNAL'
        WHERE status = 'FREE_AGENT'
          AND (team_name IS NOT NULL OR world_team_id IS NOT NULL)
          AND NOT EXISTS (
              SELECT 1 FROM contracts c
              WHERE c.player_id = players.id AND c.is_active = true
          )
        """
    )


def downgrade() -> None:
    # Collapse EXTERNAL back into FREE_AGENT — the pre-0063 meaning. The enum
    # value itself is left in place: Postgres cannot drop a value from an enum
    # type without recreating it, and leaving an unused label is harmless.
    op.execute("UPDATE players SET status = 'FREE_AGENT' WHERE status = 'EXTERNAL'")
