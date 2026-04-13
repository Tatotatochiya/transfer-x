"""Clubs, club finances, players, and contracts tables.

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-17
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ENUM as PgEnum

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Enums (DO block is safe to re-run on any Postgres version) ───────────
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE clubrole AS ENUM ('BUYER', 'SELLER', 'BOTH', 'ADMIN');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE playerposition AS ENUM ('GK', 'DEF', 'MID', 'FWD');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE playervisibility AS ENUM ('PUBLIC', 'CLUBS_ONLY', 'PRIVATE');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE playerstatus AS ENUM ('CONTRACTED', 'FREE_AGENT');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)

    # ── clubs ─────────────────────────────────────────────────────────────────
    op.create_table(
        "clubs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("country", sa.String(length=100), nullable=True),
        sa.Column("city", sa.String(length=100), nullable=True),
        sa.Column("league_name", sa.String(length=200), nullable=True),
        sa.Column("crest_url", sa.String(length=500), nullable=True),
        sa.Column(
            "role",
            PgEnum("BUYER", "SELLER", "BOTH", "ADMIN", name="clubrole", create_type=False),
            nullable=False,
            server_default="BOTH",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index(op.f("ix_clubs_user_id"), "clubs", ["user_id"], unique=True)

    # ── club_finances ─────────────────────────────────────────────────────────
    op.create_table(
        "club_finances",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("club_id", sa.Uuid(), nullable=False),
        sa.Column(
            "transfer_budget_total", sa.Numeric(precision=15, scale=2), nullable=False, server_default="0"
        ),
        sa.Column(
            "wage_budget_total_weekly", sa.Numeric(precision=15, scale=2), nullable=False, server_default="0"
        ),
        sa.Column(
            "transfer_reserved", sa.Numeric(precision=15, scale=2), nullable=False, server_default="0"
        ),
        sa.Column(
            "wage_reserved_weekly", sa.Numeric(precision=15, scale=2), nullable=False, server_default="0"
        ),
        sa.Column(
            "transfer_committed", sa.Numeric(precision=15, scale=2), nullable=False, server_default="0"
        ),
        sa.Column(
            "wage_committed_weekly", sa.Numeric(precision=15, scale=2), nullable=False, server_default="0"
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["club_id"], ["clubs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("club_id"),
    )
    op.create_index(op.f("ix_club_finances_club_id"), "club_finances", ["club_id"], unique=True)

    # ── players ───────────────────────────────────────────────────────────────
    op.create_table(
        "players",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("age", sa.Integer(), nullable=True),
        sa.Column("nationality", sa.String(length=100), nullable=True),
        sa.Column(
            "position",
            PgEnum("GK", "DEF", "MID", "FWD", name="playerposition", create_type=False),
            nullable=True,
        ),
        sa.Column("current_club_id", sa.Uuid(), nullable=True),
        sa.Column(
            "visibility",
            PgEnum("PUBLIC", "CLUBS_ONLY", "PRIVATE", name="playervisibility", create_type=False),
            nullable=False,
            server_default="PUBLIC",
        ),
        sa.Column(
            "status",
            PgEnum("CONTRACTED", "FREE_AGENT", name="playerstatus", create_type=False),
            nullable=False,
            server_default="FREE_AGENT",
        ),
        sa.Column("open_to_offers", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("photo_url", sa.String(length=500), nullable=True),
        sa.Column("vendor_id", sa.String(length=100), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
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
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["current_club_id"], ["clubs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("vendor_id"),
    )
    op.create_index(op.f("ix_players_created_by_user_id"), "players", ["created_by_user_id"])
    op.create_index(op.f("ix_players_current_club_id"), "players", ["current_club_id"])
    op.create_index(op.f("ix_players_name"), "players", ["name"])
    op.create_index(op.f("ix_players_open_to_offers"), "players", ["open_to_offers"])
    op.create_index(op.f("ix_players_position"), "players", ["position"])
    op.create_index(op.f("ix_players_status"), "players", ["status"])
    op.create_index(op.f("ix_players_visibility"), "players", ["visibility"])

    # ── contracts ─────────────────────────────────────────────────────────────
    op.create_table(
        "contracts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("player_id", sa.Uuid(), nullable=False),
        sa.Column("club_id", sa.Uuid(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("wage_weekly", sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column("release_clause", sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("notes", sa.String(length=1000), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["club_id"], ["clubs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_contracts_club_id"), "contracts", ["club_id"])
    op.create_index(op.f("ix_contracts_is_active"), "contracts", ["is_active"])
    op.create_index(op.f("ix_contracts_player_id"), "contracts", ["player_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_contracts_player_id"), table_name="contracts")
    op.drop_index(op.f("ix_contracts_is_active"), table_name="contracts")
    op.drop_index(op.f("ix_contracts_club_id"), table_name="contracts")
    op.drop_table("contracts")

    op.drop_index(op.f("ix_players_visibility"), table_name="players")
    op.drop_index(op.f("ix_players_status"), table_name="players")
    op.drop_index(op.f("ix_players_position"), table_name="players")
    op.drop_index(op.f("ix_players_open_to_offers"), table_name="players")
    op.drop_index(op.f("ix_players_name"), table_name="players")
    op.drop_index(op.f("ix_players_current_club_id"), table_name="players")
    op.drop_index(op.f("ix_players_created_by_user_id"), table_name="players")
    op.drop_table("players")

    op.drop_index(op.f("ix_club_finances_club_id"), table_name="club_finances")
    op.drop_table("club_finances")

    op.drop_index(op.f("ix_clubs_user_id"), table_name="clubs")
    op.drop_table("clubs")

    op.execute("DROP TYPE IF EXISTS playerstatus")
    op.execute("DROP TYPE IF EXISTS playervisibility")
    op.execute("DROP TYPE IF EXISTS playerposition")
    op.execute("DROP TYPE IF EXISTS clubrole")
