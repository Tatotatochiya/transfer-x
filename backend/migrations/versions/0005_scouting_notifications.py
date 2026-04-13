"""Scouting (shortlists, shortlist_items, player_interests) and notifications tables.

Revision ID: 0005
Revises: 0004
Create Date: 2026-03-17
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ENUM as PgEnum

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Enums ─────────────────────────────────────────────────────────────────
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE interestlevel AS ENUM ('WATCHING', 'INTERESTED', 'PRIORITY');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE intereststage AS ENUM ('SCOUTED', 'CONTACTED', 'NEGOTIATING', 'DROPPED');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE notificationtype AS ENUM (
                'OUTBID',
                'OFFER_RECEIVED', 'OFFER_ACCEPTED', 'OFFER_REJECTED', 'OFFER_COUNTERED', 'OFFER_EXPIRING',
                'AUCTION_BID_RECEIVED', 'AUCTION_ENDING', 'AUCTION_BID_ACCEPTED',
                'DEAL_COMPLETED', 'DEAL_COLLAPSED',
                'PLAYER_AVAILABLE'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)

    # ── shortlists ────────────────────────────────────────────────────────────
    op.create_table(
        "shortlists",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("club_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(["club_id"], ["clubs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("club_id", "name", name="uq_shortlists_club_name"),
    )
    op.create_index(op.f("ix_shortlists_club_id"), "shortlists", ["club_id"])

    # ── shortlist_items ───────────────────────────────────────────────────────
    op.create_table(
        "shortlist_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("shortlist_id", sa.Uuid(), nullable=False),
        sa.Column("player_id", sa.Uuid(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["shortlist_id"], ["shortlists.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "shortlist_id", "player_id", name="uq_shortlist_items_shortlist_player"
        ),
    )
    op.create_index(op.f("ix_shortlist_items_player_id"), "shortlist_items", ["player_id"])
    op.create_index(op.f("ix_shortlist_items_shortlist_id"), "shortlist_items", ["shortlist_id"])

    # ── player_interests ──────────────────────────────────────────────────────
    op.create_table(
        "player_interests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("club_id", sa.Uuid(), nullable=False),
        sa.Column("player_id", sa.Uuid(), nullable=False),
        sa.Column(
            "level",
            PgEnum("WATCHING", "INTERESTED", "PRIORITY", name="interestlevel", create_type=False),
            nullable=False,
            server_default="WATCHING",
        ),
        sa.Column(
            "stage",
            PgEnum("SCOUTED", "CONTACTED", "NEGOTIATING", "DROPPED", name="intereststage", create_type=False),
            nullable=False,
            server_default="SCOUTED",
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "last_touched_at",
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
        sa.ForeignKeyConstraint(["club_id"], ["clubs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("club_id", "player_id", name="uq_player_interests_club_player"),
    )
    op.create_index(op.f("ix_player_interests_club_id"), "player_interests", ["club_id"])
    op.create_index(op.f("ix_player_interests_player_id"), "player_interests", ["player_id"])

    # ── notifications ─────────────────────────────────────────────────────────
    op.create_table(
        "notifications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("recipient_user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "type",
            PgEnum(
                "OUTBID",
                "OFFER_RECEIVED",
                "OFFER_ACCEPTED",
                "OFFER_REJECTED",
                "OFFER_COUNTERED",
                "OFFER_EXPIRING",
                "AUCTION_BID_RECEIVED",
                "AUCTION_ENDING",
                "AUCTION_BID_ACCEPTED",
                "DEAL_COMPLETED",
                "DEAL_COLLAPSED",
                "PLAYER_AVAILABLE",
                name="notificationtype",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("link", sa.String(length=500), nullable=True),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("related_player_id", sa.Uuid(), nullable=True),
        sa.Column("related_club_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["recipient_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["related_club_id"], ["clubs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["related_player_id"], ["players.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_notifications_created_at"), "notifications", ["created_at"])
    op.create_index(op.f("ix_notifications_is_read"), "notifications", ["is_read"])
    op.create_index(op.f("ix_notifications_recipient_user_id"), "notifications", ["recipient_user_id"])
    op.create_index(op.f("ix_notifications_type"), "notifications", ["type"])


def downgrade() -> None:
    op.drop_index(op.f("ix_notifications_type"), table_name="notifications")
    op.drop_index(op.f("ix_notifications_recipient_user_id"), table_name="notifications")
    op.drop_index(op.f("ix_notifications_is_read"), table_name="notifications")
    op.drop_index(op.f("ix_notifications_created_at"), table_name="notifications")
    op.drop_table("notifications")

    op.drop_index(op.f("ix_player_interests_player_id"), table_name="player_interests")
    op.drop_index(op.f("ix_player_interests_club_id"), table_name="player_interests")
    op.drop_table("player_interests")

    op.drop_index(op.f("ix_shortlist_items_shortlist_id"), table_name="shortlist_items")
    op.drop_index(op.f("ix_shortlist_items_player_id"), table_name="shortlist_items")
    op.drop_table("shortlist_items")

    op.drop_index(op.f("ix_shortlists_club_id"), table_name="shortlists")
    op.drop_table("shortlists")

    op.execute("DROP TYPE IF EXISTS notificationtype")
    op.execute("DROP TYPE IF EXISTS intereststage")
    op.execute("DROP TYPE IF EXISTS interestlevel")
