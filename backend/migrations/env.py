import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# Make sure app is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings
from app.database import Base  # noqa: F401 — imports all models via metadata

# Import all models here so Alembic can detect them.
# Add new model imports as each milestone is built.
from app.auth.models import AgentProfile, PlayerProfile, RefreshToken, User  # noqa: F401
from app.clubs.models import Club, ClubFinance  # noqa: F401
from app.deals.models import Deal, DealNote  # noqa: F401
from app.fixtures.models import Fixture  # noqa: F401
from app.notifications.models import Notification, NotificationPreference  # noqa: F401
from app.offers.models import Offer, OfferEvent, OfferMessage  # noqa: F401
from app.players.models import Contract, Player, PlayerInjury, PlayerTransfer  # noqa: F401
from app.sales.models import Bid, Sale, SaleEvent  # noqa: F401
from app.scouting.models import PlayerInterest, Shortlist, ShortlistItem  # noqa: F401
from app.stats.models import PlayerForm, PlayerStats, PlayerStatsSnapshot, VendorSyncState  # noqa: F401
from app.world.models import WorldLeague, WorldTeam  # noqa: F401
from app.analytics.models import AnalyticsEvent  # noqa: F401
from app.transfer_window.models import TransferWindow  # noqa: F401

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url_sync)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
