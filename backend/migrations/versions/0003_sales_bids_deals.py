"""Sales, bids, sale_events, and deals tables.

Revision ID: 0003
Revises: 0002
Create Date: 2026-03-17
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ENUM as PgEnum

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Enums ─────────────────────────────────────────────────────────────────
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE saletype AS ENUM ('AUCTION', 'OPEN_TO_OFFERS', 'FIXED_PRICE');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE salestatus AS ENUM ('OPEN', 'CLOSED', 'WITHDRAWN', 'EXPIRED');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE saleeventtype AS ENUM (
                'CREATED', 'BID_PLACED', 'BID_REPLACED', 'BID_ACCEPTED',
                'SALE_CLOSED', 'SALE_WITHDRAWN', 'SALE_EXTENDED', 'SALE_EXPIRED'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE bidstatus AS ENUM ('ACTIVE', 'WITHDRAWN', 'ACCEPTED', 'REJECTED', 'OUTBID');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE dealstatus AS ENUM (
                'IN_PROGRESS', 'PENDING_COMPLETION', 'COMPLETED', 'COLLAPSED'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE dealstage AS ENUM ('AGREEMENT', 'PAPERWORK', 'CONFIRMED', 'COMPLETED');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)

    # ── sales ─────────────────────────────────────────────────────────────────
    op.create_table(
        "sales",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("player_id", sa.Uuid(), nullable=False),
        sa.Column("seller_club_id", sa.Uuid(), nullable=False),
        sa.Column(
            "sale_type",
            PgEnum("AUCTION", "OPEN_TO_OFFERS", "FIXED_PRICE", name="saletype", create_type=False),
            nullable=False,
        ),
        sa.Column("asking_price", sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column("reserve_price", sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column(
            "min_increment", sa.Numeric(precision=15, scale=2), nullable=False, server_default="500000"
        ),
        sa.Column("deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "status",
            PgEnum("OPEN", "CLOSED", "WITHDRAWN", "EXPIRED", name="salestatus", create_type=False),
            nullable=False,
            server_default="OPEN",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["seller_club_id"], ["clubs.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_sales_deadline"), "sales", ["deadline"])
    op.create_index(op.f("ix_sales_player_id"), "sales", ["player_id"])
    op.create_index(op.f("ix_sales_sale_type"), "sales", ["sale_type"])
    op.create_index(op.f("ix_sales_seller_club_id"), "sales", ["seller_club_id"])
    op.create_index(op.f("ix_sales_status"), "sales", ["status"])

    # ── sale_events ───────────────────────────────────────────────────────────
    op.create_table(
        "sale_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("sale_id", sa.Uuid(), nullable=False),
        sa.Column(
            "event_type",
            PgEnum(
                "CREATED",
                "BID_PLACED",
                "BID_REPLACED",
                "BID_ACCEPTED",
                "SALE_CLOSED",
                "SALE_WITHDRAWN",
                "SALE_EXTENDED",
                "SALE_EXPIRED",
                name="saleeventtype",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("actor_club_id", sa.Uuid(), nullable=True),
        sa.Column("bid_id", sa.Uuid(), nullable=True),
        sa.Column("amount", sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column("notes", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["actor_club_id"], ["clubs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["sale_id"], ["sales.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_sale_events_event_type"), "sale_events", ["event_type"])
    op.create_index(op.f("ix_sale_events_sale_id"), "sale_events", ["sale_id"])

    # ── bids ──────────────────────────────────────────────────────────────────
    op.create_table(
        "bids",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("sale_id", sa.Uuid(), nullable=False),
        sa.Column("buyer_club_id", sa.Uuid(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column("wage_offer_weekly", sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column("notes", sa.String(length=1000), nullable=True),
        sa.Column(
            "status",
            PgEnum("ACTIVE", "WITHDRAWN", "ACCEPTED", "REJECTED", "OUTBID", name="bidstatus", create_type=False),
            nullable=False,
            server_default="ACTIVE",
        ),
        sa.Column(
            "reserved_transfer_amount",
            sa.Numeric(precision=15, scale=2),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "reserved_wage_weekly",
            sa.Numeric(precision=15, scale=2),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["buyer_club_id"], ["clubs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["sale_id"], ["sales.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_bids_buyer_club_id"), "bids", ["buyer_club_id"])
    op.create_index(op.f("ix_bids_sale_id"), "bids", ["sale_id"])
    op.create_index(op.f("ix_bids_status"), "bids", ["status"])

    # ── deals ─────────────────────────────────────────────────────────────────
    op.create_table(
        "deals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("sale_id", sa.Uuid(), nullable=True),
        sa.Column("bid_id", sa.Uuid(), nullable=True),
        sa.Column("buyer_club_id", sa.Uuid(), nullable=False),
        sa.Column("seller_club_id", sa.Uuid(), nullable=False),
        sa.Column("player_id", sa.Uuid(), nullable=False),
        sa.Column("agreed_fee", sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column("agreed_wage_weekly", sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column(
            "status",
            PgEnum(
                "IN_PROGRESS", "PENDING_COMPLETION", "COMPLETED", "COLLAPSED", name="dealstatus",
                create_type=False,
            ),
            nullable=False,
            server_default="IN_PROGRESS",
        ),
        sa.Column(
            "stage",
            PgEnum("AGREEMENT", "PAPERWORK", "CONFIRMED", "COMPLETED", name="dealstage", create_type=False),
            nullable=False,
            server_default="AGREEMENT",
        ),
        sa.Column("notes", sa.String(length=2000), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["bid_id"], ["bids.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["buyer_club_id"], ["clubs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["sale_id"], ["sales.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["seller_club_id"], ["clubs.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_deals_bid_id"), "deals", ["bid_id"])
    op.create_index(op.f("ix_deals_buyer_club_id"), "deals", ["buyer_club_id"])
    op.create_index(op.f("ix_deals_player_id"), "deals", ["player_id"])
    op.create_index(op.f("ix_deals_sale_id"), "deals", ["sale_id"])
    op.create_index(op.f("ix_deals_seller_club_id"), "deals", ["seller_club_id"])
    op.create_index(op.f("ix_deals_stage"), "deals", ["stage"])
    op.create_index(op.f("ix_deals_status"), "deals", ["status"])


def downgrade() -> None:
    op.drop_index(op.f("ix_deals_status"), table_name="deals")
    op.drop_index(op.f("ix_deals_stage"), table_name="deals")
    op.drop_index(op.f("ix_deals_seller_club_id"), table_name="deals")
    op.drop_index(op.f("ix_deals_sale_id"), table_name="deals")
    op.drop_index(op.f("ix_deals_player_id"), table_name="deals")
    op.drop_index(op.f("ix_deals_buyer_club_id"), table_name="deals")
    op.drop_index(op.f("ix_deals_bid_id"), table_name="deals")
    op.drop_table("deals")

    op.drop_index(op.f("ix_bids_status"), table_name="bids")
    op.drop_index(op.f("ix_bids_sale_id"), table_name="bids")
    op.drop_index(op.f("ix_bids_buyer_club_id"), table_name="bids")
    op.drop_table("bids")

    op.drop_index(op.f("ix_sale_events_sale_id"), table_name="sale_events")
    op.drop_index(op.f("ix_sale_events_event_type"), table_name="sale_events")
    op.drop_table("sale_events")

    op.drop_index(op.f("ix_sales_status"), table_name="sales")
    op.drop_index(op.f("ix_sales_seller_club_id"), table_name="sales")
    op.drop_index(op.f("ix_sales_sale_type"), table_name="sales")
    op.drop_index(op.f("ix_sales_player_id"), table_name="sales")
    op.drop_index(op.f("ix_sales_deadline"), table_name="sales")
    op.drop_table("sales")

    op.execute("DROP TYPE IF EXISTS dealstage")
    op.execute("DROP TYPE IF EXISTS dealstatus")
    op.execute("DROP TYPE IF EXISTS bidstatus")
    op.execute("DROP TYPE IF EXISTS saleeventtype")
    op.execute("DROP TYPE IF EXISTS salestatus")
    op.execute("DROP TYPE IF EXISTS saletype")
