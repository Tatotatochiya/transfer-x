"""TRA-134: client-roster alerts — Mandate alert config + client_alerts table.

Revision ID: 0046
Revises: 0045
Create Date: 2026-07-03
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision: str = "0046"
down_revision: Union[str, None] = "0045"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("mandates", sa.Column("alert_contract_expiry_enabled", sa.Boolean(), nullable=False, server_default="true"))
    op.add_column("mandates", sa.Column("alert_contract_expiry_months", sa.Integer(), nullable=False, server_default="12"))
    op.add_column("mandates", sa.Column("alert_valuation_change_enabled", sa.Boolean(), nullable=False, server_default="true"))
    op.add_column("mandates", sa.Column("alert_valuation_change_pct", sa.Numeric(5, 4), nullable=False, server_default="0.10"))
    op.add_column("mandates", sa.Column("alert_club_interest_enabled", sa.Boolean(), nullable=False, server_default="true"))
    op.add_column("mandates", sa.Column("last_seen_market_value", sa.Numeric(15, 2), nullable=True))
    op.add_column("mandates", sa.Column("last_seen_interest_club_ids", sa.JSON(), nullable=False, server_default="[]"))

    op.execute("ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'CLIENT_ALERT'")
    op.execute("CREATE TYPE alerttype AS ENUM ('CONTRACT_EXPIRY', 'VALUATION_CHANGE', 'CLUB_INTEREST')")
    op.execute("CREATE TYPE alertseverity AS ENUM ('RED', 'AMBER', 'GREEN')")

    op.create_table(
        "client_alerts",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("mandate_id", sa.Uuid(as_uuid=True), sa.ForeignKey("mandates.id", ondelete="CASCADE"), nullable=False),
        sa.Column("agent_id", sa.Uuid(as_uuid=True), sa.ForeignKey("agent_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("player_id", sa.Uuid(as_uuid=True), sa.ForeignKey("players.id", ondelete="CASCADE"), nullable=False),
        sa.Column("alert_type", pg.ENUM("CONTRACT_EXPIRY", "VALUATION_CHANGE", "CLUB_INTEREST", name="alerttype", create_type=False), nullable=False),
        sa.Column("severity", pg.ENUM("RED", "AMBER", "GREEN", name="alertseverity", create_type=False), nullable=False),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("context", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("is_read", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_client_alerts_mandate_id", "client_alerts", ["mandate_id"])
    op.create_index("ix_client_alerts_agent_id", "client_alerts", ["agent_id"])
    op.create_index("ix_client_alerts_player_id", "client_alerts", ["player_id"])
    op.create_index("ix_client_alerts_alert_type", "client_alerts", ["alert_type"])
    op.create_index("ix_client_alerts_created_at", "client_alerts", ["created_at"])


def downgrade() -> None:
    op.drop_table("client_alerts")
    op.execute("DROP TYPE alertseverity")
    op.execute("DROP TYPE alerttype")
    op.drop_column("mandates", "last_seen_interest_club_ids")
    op.drop_column("mandates", "last_seen_market_value")
    op.drop_column("mandates", "alert_club_interest_enabled")
    op.drop_column("mandates", "alert_valuation_change_pct")
    op.drop_column("mandates", "alert_valuation_change_enabled")
    op.drop_column("mandates", "alert_contract_expiry_months")
    op.drop_column("mandates", "alert_contract_expiry_enabled")
    # notificationtype enum value removal is a no-op in Postgres.
