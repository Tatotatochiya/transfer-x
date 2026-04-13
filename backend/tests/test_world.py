"""M6 — World tests."""

import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient

from tests.conftest import _auth_headers, _register


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def world_user(client: AsyncClient) -> dict:
    return await _register(client, "world@test.com", club_name="World FC")


def _league_payload(vendor="api-football", league_id="39", name="Premier League", **kwargs):
    payload = {"vendor": vendor, "league_id": league_id, "name": name}
    payload.update(kwargs)
    return payload


# ── Tests ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_leagues_empty(client: AsyncClient):
    """GET /world/leagues unauthenticated, returns empty list."""
    resp = await client.get("/world/leagues")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_create_league(client: AsyncClient, world_user: dict):
    """POST /world/leagues authenticated, returns league data."""
    headers = _auth_headers(world_user)
    payload = _league_payload(country="England", season="2024/25")
    resp = await client.post("/world/leagues", json=payload, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["vendor"] == "api-football"
    assert data["league_id"] == "39"
    assert data["name"] == "Premier League"
    assert data["country"] == "England"
    assert data["season"] == "2024/25"
    assert "id" in data
    assert "created_at" in data


@pytest.mark.asyncio
async def test_upsert_league_updates_existing(client: AsyncClient, world_user: dict):
    """POST same vendor+league_id updates name."""
    headers = _auth_headers(world_user)
    payload = _league_payload(name="Premier League")
    resp1 = await client.post("/world/leagues", json=payload, headers=headers)
    assert resp1.status_code == 200
    league_id = resp1.json()["id"]

    payload2 = _league_payload(name="English Premier League")
    resp2 = await client.post("/world/leagues", json=payload2, headers=headers)
    assert resp2.status_code == 200
    data = resp2.json()
    assert data["id"] == league_id
    assert data["name"] == "English Premier League"

    # Verify only one league exists
    resp_list = await client.get("/world/leagues")
    assert len(resp_list.json()) == 1


@pytest.mark.asyncio
async def test_list_leagues(client: AsyncClient, world_user: dict):
    """Create 3 leagues, GET returns all 3."""
    headers = _auth_headers(world_user)
    await client.post("/world/leagues", json=_league_payload(vendor="v1", league_id="1", name="League 1"), headers=headers)
    await client.post("/world/leagues", json=_league_payload(vendor="v1", league_id="2", name="League 2"), headers=headers)
    await client.post("/world/leagues", json=_league_payload(vendor="v2", league_id="1", name="League 3"), headers=headers)

    resp = await client.get("/world/leagues")
    assert resp.status_code == 200
    assert len(resp.json()) == 3


@pytest.mark.asyncio
async def test_filter_by_vendor(client: AsyncClient, world_user: dict):
    """Filter returns only matching vendor."""
    headers = _auth_headers(world_user)
    await client.post("/world/leagues", json=_league_payload(vendor="v1", league_id="1", name="L1"), headers=headers)
    await client.post("/world/leagues", json=_league_payload(vendor="v1", league_id="2", name="L2"), headers=headers)
    await client.post("/world/leagues", json=_league_payload(vendor="v2", league_id="1", name="L3"), headers=headers)

    resp = await client.get("/world/leagues", params={"vendor": "v1"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert all(l["vendor"] == "v1" for l in data)


@pytest.mark.asyncio
async def test_filter_by_country(client: AsyncClient, world_user: dict):
    """Filter by country."""
    headers = _auth_headers(world_user)
    await client.post(
        "/world/leagues",
        json=_league_payload(vendor="v1", league_id="1", name="PL", country="England"),
        headers=headers,
    )
    await client.post(
        "/world/leagues",
        json=_league_payload(vendor="v1", league_id="2", name="La Liga", country="Spain"),
        headers=headers,
    )

    resp = await client.get("/world/leagues", params={"country": "England"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["country"] == "England"


@pytest.mark.asyncio
async def test_filter_by_season(client: AsyncClient, world_user: dict):
    """Filter by season."""
    headers = _auth_headers(world_user)
    await client.post(
        "/world/leagues",
        json=_league_payload(vendor="v1", league_id="1", name="PL 24/25", season="2024/25"),
        headers=headers,
    )
    await client.post(
        "/world/leagues",
        json=_league_payload(vendor="v1", league_id="2", name="PL 23/24", season="2023/24"),
        headers=headers,
    )

    resp = await client.get("/world/leagues", params={"season": "2024/25"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["season"] == "2024/25"


@pytest.mark.asyncio
async def test_search_by_name(client: AsyncClient, world_user: dict):
    """Search param does substring match on name."""
    headers = _auth_headers(world_user)
    await client.post("/world/leagues", json=_league_payload(vendor="v1", league_id="1", name="Premier League"), headers=headers)
    await client.post("/world/leagues", json=_league_payload(vendor="v1", league_id="2", name="La Liga"), headers=headers)
    await client.post("/world/leagues", json=_league_payload(vendor="v1", league_id="3", name="Bundesliga"), headers=headers)

    resp = await client.get("/world/leagues", params={"search": "liga"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    names = {l["name"] for l in data}
    assert "La Liga" in names
    assert "Bundesliga" in names


@pytest.mark.asyncio
async def test_get_league_by_id(client: AsyncClient, world_user: dict):
    """GET /world/leagues/{id} returns the league."""
    headers = _auth_headers(world_user)
    create_resp = await client.post(
        "/world/leagues",
        json=_league_payload(name="Serie A"),
        headers=headers,
    )
    league_id = create_resp.json()["id"]

    resp = await client.get(f"/world/leagues/{league_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == league_id
    assert resp.json()["name"] == "Serie A"


@pytest.mark.asyncio
async def test_get_league_not_found(client: AsyncClient):
    """GET nonexistent UUID → 404."""
    fake_id = str(uuid.uuid4())
    resp = await client.get(f"/world/leagues/{fake_id}")
    assert resp.status_code == 404
