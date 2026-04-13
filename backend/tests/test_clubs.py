"""Club endpoint tests — M2."""

import pytest
from httpx import AsyncClient

from tests.conftest import _register, _auth_headers

pytestmark = pytest.mark.asyncio


async def test_register_creates_club(client: AsyncClient):
    tokens = await _register(client, "newclub@test.com", club_name="My FC")
    resp = await client.get("/clubs/me", headers=_auth_headers(tokens))
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "My FC"
    assert data["role"] == "BOTH"
    assert data["finance"] is not None


async def test_register_club_name_defaults_to_email_prefix(client: AsyncClient):
    tokens = await _register(client, "arsenal@test.com", club_name="")
    resp = await client.get("/clubs/me", headers=_auth_headers(tokens))
    assert resp.json()["name"] == "arsenal"


async def test_get_my_club_requires_auth(client: AsyncClient):
    resp = await client.get("/clubs/me")
    assert resp.status_code == 401


async def test_patch_my_club(client: AsyncClient, auth_headers: dict):
    resp = await client.patch(
        "/clubs/me",
        json={"name": "Updated FC", "country": "England", "city": "London"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Updated FC"
    assert data["country"] == "England"
    assert data["city"] == "London"


async def test_patch_my_club_partial(client: AsyncClient, auth_headers: dict):
    """Omitted fields are not overwritten."""
    await client.patch("/clubs/me", json={"country": "Spain"}, headers=auth_headers)
    resp = await client.get("/clubs/me", headers=auth_headers)
    assert resp.json()["country"] == "Spain"
    assert resp.json()["name"] == "Test Club"  # unchanged


async def test_list_clubs(client: AsyncClient):
    await _register(client, "club1@test.com", club_name="Alpha FC")
    await _register(client, "club2@test.com", club_name="Beta United")
    resp = await client.get("/clubs")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 2
    names = [c["name"] for c in data["items"]]
    assert "Alpha FC" in names
    assert "Beta United" in names


async def test_list_clubs_search(client: AsyncClient):
    await _register(client, "a@test.com", club_name="Zeta Athletic")
    await _register(client, "b@test.com", club_name="Omega City")
    resp = await client.get("/clubs?search=Zeta")
    data = resp.json()
    assert all("Zeta" in c["name"] for c in data["items"])


async def test_get_club_by_id(client: AsyncClient, auth_headers: dict):
    # Get our own club's ID first
    my_club = (await client.get("/clubs/me", headers=auth_headers)).json()
    club_id = my_club["id"]

    resp = await client.get(f"/clubs/{club_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == club_id


async def test_get_club_not_found(client: AsyncClient):
    import uuid
    resp = await client.get(f"/clubs/{uuid.uuid4()}")
    assert resp.status_code == 404


async def test_club_finance_initial_values(client: AsyncClient, auth_headers: dict):
    resp = await client.get("/clubs/me", headers=auth_headers)
    finance = resp.json()["finance"]
    assert float(finance["transfer_budget_total"]) == 0.0
    assert float(finance["transfer_remaining"]) == 0.0
    assert float(finance["wage_remaining_weekly"]) == 0.0
