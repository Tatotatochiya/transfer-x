"""Offers, offer_messages, offer_events, deal_notes; offer_id on deals.

Revision ID: 0004
Revises: 0003
Create Date: 2026-03-17
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ENUM as PgEnum

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Enums ─────────────────────────────────────────────────────────────────
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE offerstatus AS ENUM (
                'DRAFT', 'SENT', 'COUNTERED', 'ACCEPTED', 'REJECTED', 'WITHDRAWN', 'EXPIRED'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE offereventtype AS ENUM (
                'CREATED', 'SENT', 'COUNTERED', 'ACCEPTED', 'REJECTED', 'WITHDRAWN', 'EXPIRED', 'MESSAGE'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)

    # ── offers ─────────────────────────────────────────────────────────────────
    op.create_table(
        "offers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("player_id", sa.Uuid(), nullable=False),
        sa.Column("sale_id", sa.Uuid(), nullable=True),
        sa.Column("from_club_id", sa.Uuid(), nullable=False),
        sa.Column("to_club_id", sa.Uuid(), nullable=True),
        sa.Column("fee_amount", sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column("wage_weekly", sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column("contract_years", sa.Integer(), nullable=True),
        sa.Column("contract_end_date", sa.Date(), nullable=True),
        sa.Column("add_ons", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column(
            "status",
            PgEnum(
                "DRAFT", "SENT", "COUNTERED", "ACCEPTED", "REJECTED", "WITHDRAWN", "EXPIRED",
                name="offerstatus",
                create_type=False,
            ),
            nullable=False,
            server_default="DRAFT",
        ),
        sa.Column(
            "reserved_transfer_amount",
            sa.Numeric(precision=15, scale=2),
            nullable=False,
            server_default="0",
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "last_action_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["from_club_id"], ["clubs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["sale_id"], ["sales.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["to_club_id"], ["clubs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_offers_expires_at"), "offers", ["expires_at"])
    op.create_index(op.f("ix_offers_from_club_id"), "offers", ["from_club_id"])
    op.create_index(op.f("ix_offers_player_id"), "offers", ["player_id"])
    op.create_index(op.f("ix_offers_sale_id"), "offers", ["sale_id"])
    op.create_index(op.f("ix_offers_status"), "offers", ["status"])
    op.create_index(op.f("ix_offers_to_club_id"), "offers", ["to_club_id"])

    # ── offer_messages ────────────────────────────────────────────────────────
    op.create_table(
        "offer_messages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("offer_id", sa.Uuid(), nullable=False),
        sa.Column("sender_club_id", sa.Uuid(), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["offer_id"], ["offers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["sender_club_id"], ["clubs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_offer_messages_offer_id"), "offer_messages", ["offer_id"])

    # ── offer_events ──────────────────────────────────────────────────────────
    op.create_table(
        "offer_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("offer_id", sa.Uuid(), nullable=False),
        sa.Column(
            "event_type",
            PgEnum(
                "CREATED", "SENT", "COUNTERED", "ACCEPTED", "REJECTED", "WITHDRAWN", "EXPIRED", "MESSAGE",
                name="offereventtype",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("actor_club_id", sa.Uuid(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["actor_club_id"], ["clubs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["offer_id"], ["offers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_offer_events_event_type"), "offer_events", ["event_type"])
    op.create_index(op.f("ix_offer_events_offer_id"), "offer_events", ["offer_id"])

    # ── Add offer_id + completed_at to deals ──────────────────────────────────
    op.add_column("deals", sa.Column("offer_id", sa.Uuid(), nullable=True))
    op.add_column("deals", sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key(
        "fk_deals_offer_id", "deals", "offers", ["offer_id"], ["id"], ondelete="RESTRICT"
    )
    op.create_index(op.f("ix_deals_offer_id"), "deals", ["offer_id"])

    # seller_club_id already NOT NULL in 0003 — make nullable for free-agent deals
    op.alter_column("deals", "seller_club_id", nullable=True)

    # ── deal_notes ────────────────────────────────────────────────────────────
    op.create_table(
        "deal_notes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("deal_id", sa.Uuid(), nullable=False),
        sa.Column("author_club_id", sa.Uuid(), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["author_club_id"], ["clubs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["deal_id"], ["deals.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_deal_notes_deal_id"), "deal_notes", ["deal_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_deal_notes_deal_id"), table_name="deal_notes")
    op.drop_table("deal_notes")

    op.drop_index(op.f("ix_deals_offer_id"), table_name="deals")
    op.drop_constraint("fk_deals_offer_id", "deals", type_="foreignkey")
    op.drop_column("deals", "completed_at")
    op.drop_column("deals", "offer_id")

    op.drop_index(op.f("ix_offer_events_offer_id"), table_name="offer_events")
    op.drop_index(op.f("ix_offer_events_event_type"), table_name="offer_events")
    op.drop_table("offer_events")

    op.drop_index(op.f("ix_offer_messages_offer_id"), table_name="offer_messages")
    op.drop_table("offer_messages")

    op.drop_index(op.f("ix_offers_to_club_id"), table_name="offers")
    op.drop_index(op.f("ix_offers_status"), table_name="offers")
    op.drop_index(op.f("ix_offers_sale_id"), table_name="offers")
    op.drop_index(op.f("ix_offers_player_id"), table_name="offers")
    op.drop_index(op.f("ix_offers_from_club_id"), table_name="offers")
    op.drop_index(op.f("ix_offers_expires_at"), table_name="offers")
    op.drop_table("offers")

    op.execute("DROP TYPE IF EXISTS offereventtype")
    op.execute("DROP TYPE IF EXISTS offerstatus")
