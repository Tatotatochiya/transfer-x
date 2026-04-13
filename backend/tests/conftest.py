import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base, get_db
from app.main import app

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


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
