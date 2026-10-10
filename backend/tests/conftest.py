import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.database import Base, get_db
from app.main import app

# The fixtures register clubs directly through POST /auth/register. Real
# environments are invitation-only (settings.allow_club_self_registration
# defaults to False); the invitation flow has its own tests.
settings.allow_club_self_registration = True
# Likewise players: real environments invite them from their club.
settings.allow_player_self_registration = True
# No phone pushes from tests: a commit would start a real send, in its own
# session on the real database. tests/test_push.py turns them on for itself.
settings.vapid_public_key = settings.vapid_private_key = settings.vapid_subject = None
# No live API-Football calls (the admin Health page asks it for today's
# usage); the vendor tests set a key and mock the client themselves.
settings.apisports_key = None
# No live exchange-rate fetches: the estimates use the fallback rates.
settings.fx_rates_url = None

# No Slack posts from tests (tests/test_monitoring.py catches them itself).
settings.slack_webhook_url = None

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


def _no_real_database():
    raise RuntimeError("monitoring tried to write outside the test database")


@pytest.fixture(autouse=True)
def _monitoring_sessions(request):
    """Monitoring writes in its own sessions (job runs, errors, request
    figures). Point them at the test's database, or at nothing: never at the
    real one. Those writes are best effort, so a refused one is skipped."""
    from app import monitoring

    if "db_engine" in request.fixturenames:
        monitoring.session_factory = async_sessionmaker(request.getfixturevalue("db_engine"), expire_on_commit=False)
    else:
        monitoring.session_factory = _no_real_database
    yield
    monitoring.session_factory = None


@pytest_asyncio.fixture(scope="function")
async def db_engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db(db_engine):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture(scope="function")
async def client(db: AsyncSession):
    """HTTP client with the DB dependency overridden to the test SQLite DB."""

    async def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


# ── Shared auth helpers ───────────────────────────────────────────────────────


async def _register(client: AsyncClient, email: str, password: str = "password123", club_name: str = "") -> dict:
    resp = await client.post(
        "/auth/register",
        json={"email": email, "password": password, "club_name": club_name or email.split("@")[0]},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _auth_headers(tokens: dict) -> dict:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


@pytest_asyncio.fixture
async def user_tokens(client: AsyncClient) -> dict:
    """A registered user with a club (role=BOTH by default)."""
    return await _register(client, "user@test.com", club_name="Test Club")


@pytest_asyncio.fixture
async def auth_headers(user_tokens: dict) -> dict:
    return _auth_headers(user_tokens)
