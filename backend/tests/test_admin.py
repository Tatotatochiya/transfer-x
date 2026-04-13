"""Admin endpoint tests — M7."""

import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select

from tests.conftest import _auth_headers, _register

pytestmark = pytest.mark.asyncio


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def superuser(client, db):
    """Register a user then promote to superuser directly in DB."""
    tokens = await _register(client, "admin@test.com", club_name="Admin Club")
    from app.auth.models import User

    result = await db.execute(select(User).where(User.email == "admin@test.com"))
    user = result.scalar_one()
    user.is_superuser = True
    await db.commit()
    return tokens


@pytest_asyncio.fixture
async def regular_user(client):
    return await _register(client, "regular@test.com", club_name="Regular Club")


def _su_headers(tokens: dict) -> dict:
    return _auth_headers(tokens)


# ── Tests ─────────────────────────────────────────────────────────────────────


async def test_admin_requires_superuser(client: AsyncClient, regular_user: dict):
    resp = await client.get("/admin/stats", headers=_auth_headers(regular_user))
    assert resp.status_code == 403


async def test_admin_stats(client: AsyncClient, superuser: dict):
    resp = await client.get("/admin/stats", headers=_su_headers(superuser))
    assert resp.status_code == 200
    data = resp.json()
    for key in ("total_users", "total_clubs", "total_players", "active_sales", "open_offers", "active_deals"):
        assert key in data
        assert isinstance(data[key], int)
        assert data[key] >= 0


async def test_list_users(client: AsyncClient, superuser: dict):
    resp = await client.get("/admin/users", headers=_su_headers(superuser))
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] >= 1
    assert isinstance(data["items"], list)


async def test_list_users_search(client: AsyncClient, superuser: dict):
    resp = await client.get("/admin/users?search=admin", headers=_su_headers(superuser))
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    # All returned emails contain "admin"
    for item in data["items"]:
        assert "admin" in item["email"]


async def test_get_user_by_id(client: AsyncClient, superuser: dict, db):
    from app.auth.models import User

    result = await db.execute(select(User).where(User.email == "admin@test.com"))
    user = result.scalar_one()

    resp = await client.get(f"/admin/users/{user.id}", headers=_su_headers(superuser))
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == "admin@test.com"
    assert data["is_superuser"] is True


async def test_get_user_not_found(client: AsyncClient, superuser: dict):
    random_id = uuid.uuid4()
    resp = await client.get(f"/admin/users/{random_id}", headers=_su_headers(superuser))
    assert resp.status_code == 404


async def test_update_user_deactivate(client: AsyncClient, superuser: dict, regular_user: dict, db):
    from app.auth.models import User

    result = await db.execute(select(User).where(User.email == "regular@test.com"))
    user = result.scalar_one()

    resp = await client.patch(
        f"/admin/users/{user.id}",
        json={"is_active": False},
        headers=_su_headers(superuser),
    )
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False


async def test_list_clubs(client: AsyncClient, superuser: dict):
    resp = await client.get("/admin/clubs", headers=_su_headers(superuser))
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert data["total"] >= 1


async def test_list_clubs_search(client: AsyncClient, superuser: dict):
    resp = await client.get("/admin/clubs?search=Admin", headers=_su_headers(superuser))
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    for item in data["items"]:
        assert "admin" in item["name"].lower()


async def test_get_club_detail(client: AsyncClient, superuser: dict, db):
    from app.clubs.models import Club

    result = await db.execute(select(Club).where(Club.name == "Admin Club"))
    club = result.scalar_one()

    resp = await client.get(f"/admin/clubs/{club.id}", headers=_su_headers(superuser))
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Admin Club"
    assert "finance" in data  # may be null but key must exist


async def test_update_club_role(client: AsyncClient, superuser: dict, db):
    from app.clubs.models import Club

    result = await db.execute(select(Club).where(Club.name == "Admin Club"))
    club = result.scalar_one()

    resp = await client.patch(
        f"/admin/clubs/{club.id}",
        json={"role": "BUYER"},
        headers=_su_headers(superuser),
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "BUYER"


async def test_update_club_finances(client: AsyncClient, superuser: dict):
    # Get superuser's club via /clubs/me
    resp = await client.get("/clubs/me", headers=_su_headers(superuser))
    assert resp.status_code == 200
    club_id = resp.json()["id"]

    resp = await client.put(
        f"/admin/clubs/{club_id}/finances",
        json={"transfer_budget_total": 50000000},
        headers=_su_headers(superuser),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert float(data["transfer_budget_total"]) == 50000000.0


async def test_admin_list_players(client: AsyncClient, superuser: dict, db):
    # Create a player via the API
    resp = await client.post(
        "/players",
        json={"name": "Private Player", "age": 25, "position": "FWD", "visibility": "PRIVATE"},
        headers=_su_headers(superuser),
    )
    assert resp.status_code == 201
    player_id = resp.json()["id"]

    # Verify via admin endpoint
    resp = await client.get("/admin/players", headers=_su_headers(superuser))
    assert resp.status_code == 200
    data = resp.json()
    player_ids = [p["id"] for p in data["items"]]
    assert player_id in player_ids


async def test_admin_list_sales(client: AsyncClient, superuser: dict, db):
    from app.clubs.models import Club
    from app.players.models import Player
    from app.sales.service import create_sale
    from app.sales.models import SaleType

    # Get superuser's club
    result = await db.execute(select(Club).where(Club.name == "Admin Club"))
    club = result.scalar_one()

    # Create a player
    from app.players.service import create_player
    player = await create_player(db, created_by_user_id=club.user_id, name="Sale Player")
    await db.flush()

    # Create a sale
    await create_sale(
        db,
        player_id=player.id,
        seller_club_id=club.id,
        sale_type=SaleType.FIXED_PRICE,
    )
    await db.commit()

    resp = await client.get("/admin/sales", headers=_su_headers(superuser))
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert isinstance(data["items"], list)


async def test_admin_stats_counts_correctly(client: AsyncClient, superuser: dict, db):
    # Register two more users
    await _register(client, "extra1@test.com", club_name="Extra Club 1")
    await _register(client, "extra2@test.com", club_name="Extra Club 2")

    # Create a player
    resp = await client.post(
        "/players",
        json={"name": "Stats Test Player", "age": 22, "position": "MID"},
        headers=_su_headers(superuser),
    )
    assert resp.status_code == 201

    # Check stats
    resp = await client.get("/admin/stats", headers=_su_headers(superuser))
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_users"] >= 2
    assert data["total_players"] >= 1
