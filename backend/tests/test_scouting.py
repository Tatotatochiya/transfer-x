"""M5 — Scouting tests."""

import pytest
import pytest_asyncio
from httpx import AsyncClient

from tests.conftest import _auth_headers, _register


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def scout_user(client: AsyncClient) -> dict:
    return await _register(client, "scout@test.com", club_name="Scout FC")


@pytest_asyncio.fixture
async def other_user(client: AsyncClient) -> dict:
    return await _register(client, "other_scout@test.com", club_name="Other FC")


async def _create_player(client: AsyncClient, headers: dict, name: str = "Target Player") -> dict:
    resp = await client.post("/players", json={"name": name, "position": "MID"}, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _create_shortlist(client: AsyncClient, headers: dict, name: str = "My Watchlist") -> dict:
    resp = await client.post("/scouting/shortlists", json={"name": name}, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


# ── Shortlist CRUD ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_shortlist(client: AsyncClient, scout_user: dict):
    headers = _auth_headers(scout_user)
    resp = await client.post("/scouting/shortlists", json={"name": "Top Targets"}, headers=headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Top Targets"
    assert data["items"] == []


@pytest.mark.asyncio
async def test_create_duplicate_shortlist_name_fails(client: AsyncClient, scout_user: dict):
    headers = _auth_headers(scout_user)
    await _create_shortlist(client, headers, "Watchlist")
    resp = await client.post("/scouting/shortlists", json={"name": "Watchlist"}, headers=headers)
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_list_shortlists(client: AsyncClient, scout_user: dict):
    headers = _auth_headers(scout_user)
    await _create_shortlist(client, headers, "List A")
    await _create_shortlist(client, headers, "List B")
    resp = await client.get("/scouting/shortlists", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_get_shortlist_by_id(client: AsyncClient, scout_user: dict):
    headers = _auth_headers(scout_user)
    sl = await _create_shortlist(client, headers)
    resp = await client.get(f"/scouting/shortlists/{sl['id']}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == sl["id"]


@pytest.mark.asyncio
async def test_cannot_access_other_clubs_shortlist(client: AsyncClient, scout_user: dict, other_user: dict):
    headers = _auth_headers(scout_user)
    sl = await _create_shortlist(client, headers)
    resp = await client.get(f"/scouting/shortlists/{sl['id']}", headers=_auth_headers(other_user))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_update_shortlist(client: AsyncClient, scout_user: dict):
    headers = _auth_headers(scout_user)
    sl = await _create_shortlist(client, headers, "Old Name")
    resp = await client.patch(
        f"/scouting/shortlists/{sl['id']}",
        json={"name": "New Name", "description": "Updated desc"},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "New Name"
    assert data["description"] == "Updated desc"


@pytest.mark.asyncio
async def test_delete_shortlist(client: AsyncClient, scout_user: dict):
    headers = _auth_headers(scout_user)
    sl = await _create_shortlist(client, headers)
    resp = await client.delete(f"/scouting/shortlists/{sl['id']}", headers=headers)
    assert resp.status_code == 204

    resp = await client.get(f"/scouting/shortlists/{sl['id']}", headers=headers)
    assert resp.status_code == 404


# ── Shortlist items ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_add_player_to_shortlist(client: AsyncClient, scout_user: dict):
    headers = _auth_headers(scout_user)
    player = await _create_player(client, headers)
    sl = await _create_shortlist(client, headers)

    resp = await client.post(
        f"/scouting/shortlists/{sl['id']}/items",
        json={"player_id": player["id"], "priority": 2, "notes": "Very fast"},
        headers=headers,
    )
    assert resp.status_code == 201
    item = resp.json()
    assert item["player_id"] == player["id"]
    assert item["priority"] == 2
    assert item["notes"] == "Very fast"


@pytest.mark.asyncio
async def test_add_same_player_twice_fails(client: AsyncClient, scout_user: dict):
    headers = _auth_headers(scout_user)
    player = await _create_player(client, headers)
    sl = await _create_shortlist(client, headers)

    await client.post(
        f"/scouting/shortlists/{sl['id']}/items",
        json={"player_id": player["id"]},
        headers=headers,
    )
    resp = await client.post(
        f"/scouting/shortlists/{sl['id']}/items",
        json={"player_id": player["id"]},
        headers=headers,
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_update_shortlist_item(client: AsyncClient, scout_user: dict):
    headers = _auth_headers(scout_user)
    player = await _create_player(client, headers)
    sl = await _create_shortlist(client, headers)
    await client.post(
        f"/scouting/shortlists/{sl['id']}/items",
        json={"player_id": player["id"], "priority": 3},
        headers=headers,
    )
    resp = await client.patch(
        f"/scouting/shortlists/{sl['id']}/items/{player['id']}",
        json={"priority": 1, "notes": "Top priority"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["priority"] == 1


@pytest.mark.asyncio
async def test_remove_player_from_shortlist(client: AsyncClient, scout_user: dict):
    headers = _auth_headers(scout_user)
    player = await _create_player(client, headers)
    sl = await _create_shortlist(client, headers)
    await client.post(
        f"/scouting/shortlists/{sl['id']}/items",
        json={"player_id": player["id"]},
        headers=headers,
    )
    resp = await client.delete(
        f"/scouting/shortlists/{sl['id']}/items/{player['id']}", headers=headers
    )
    assert resp.status_code == 204

    # Confirm removed
    sl_resp = await client.get(f"/scouting/shortlists/{sl['id']}", headers=headers)
    assert sl_resp.json()["items"] == []


@pytest.mark.asyncio
async def test_invalid_priority_rejected(client: AsyncClient, scout_user: dict):
    headers = _auth_headers(scout_user)
    player = await _create_player(client, headers)
    sl = await _create_shortlist(client, headers)
    resp = await client.post(
        f"/scouting/shortlists/{sl['id']}/items",
        json={"player_id": player["id"], "priority": 10},
        headers=headers,
    )
    assert resp.status_code == 422


# ── Player interests ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_set_interest(client: AsyncClient, scout_user: dict):
    headers = _auth_headers(scout_user)
    player = await _create_player(client, headers)

    resp = await client.put(
        f"/scouting/interests/{player['id']}",
        json={"level": "PRIORITY", "stage": "CONTACTED", "notes": "Called agent"},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["level"] == "PRIORITY"
    assert data["stage"] == "CONTACTED"


@pytest.mark.asyncio
async def test_update_interest_upserts(client: AsyncClient, scout_user: dict):
    headers = _auth_headers(scout_user)
    player = await _create_player(client, headers)

    await client.put(
        f"/scouting/interests/{player['id']}",
        json={"level": "WATCHING", "stage": "SCOUTED"},
        headers=headers,
    )
    resp = await client.put(
        f"/scouting/interests/{player['id']}",
        json={"level": "PRIORITY", "stage": "NEGOTIATING"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["level"] == "PRIORITY"

    # Should still be just one interest record
    interests_resp = await client.get("/scouting/interests", headers=headers)
    assert interests_resp.json()[0]["player_id"] == player["id"]
    assert len(interests_resp.json()) == 1


@pytest.mark.asyncio
async def test_clear_interest(client: AsyncClient, scout_user: dict):
    headers = _auth_headers(scout_user)
    player = await _create_player(client, headers)

    await client.put(
        f"/scouting/interests/{player['id']}",
        json={"level": "WATCHING", "stage": "SCOUTED"},
        headers=headers,
    )
    resp = await client.delete(f"/scouting/interests/{player['id']}", headers=headers)
    assert resp.status_code == 204

    interests_resp = await client.get("/scouting/interests", headers=headers)
    assert interests_resp.json() == []


@pytest.mark.asyncio
async def test_list_interests(client: AsyncClient, scout_user: dict):
    headers = _auth_headers(scout_user)
    p1 = await _create_player(client, headers, "Player One")
    p2 = await _create_player(client, headers, "Player Two")

    await client.put(f"/scouting/interests/{p1['id']}", json={"level": "WATCHING", "stage": "SCOUTED"}, headers=headers)
    await client.put(f"/scouting/interests/{p2['id']}", json={"level": "PRIORITY", "stage": "CONTACTED"}, headers=headers)

    resp = await client.get("/scouting/interests", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 2


# ── Targets dashboard ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_targets_combines_shortlists_and_interests(client: AsyncClient, scout_user: dict):
    headers = _auth_headers(scout_user)
    p1 = await _create_player(client, headers, "Target A")
    p2 = await _create_player(client, headers, "Target B")
    p3 = await _create_player(client, headers, "Target C")

    sl = await _create_shortlist(client, headers, "Main List")
    await client.post(f"/scouting/shortlists/{sl['id']}/items", json={"player_id": p1["id"]}, headers=headers)
    await client.post(f"/scouting/shortlists/{sl['id']}/items", json={"player_id": p2["id"]}, headers=headers)

    await client.put(f"/scouting/interests/{p2['id']}", json={"level": "PRIORITY", "stage": "CONTACTED"}, headers=headers)
    await client.put(f"/scouting/interests/{p3['id']}", json={"level": "INTERESTED", "stage": "SCOUTED"}, headers=headers)

    resp = await client.get("/scouting/targets", headers=headers)
    assert resp.status_code == 200
    targets = resp.json()
    assert len(targets) == 3  # p1, p2, p3 — deduplicated

    p2_target = next(t for t in targets if t["player_id"] == p2["id"])
    assert p2_target["interest_level"] == "PRIORITY"
    assert "Main List" in p2_target["on_shortlists"]


@pytest.mark.asyncio
async def test_empty_targets(client: AsyncClient, scout_user: dict):
    resp = await client.get("/scouting/targets", headers=_auth_headers(scout_user))
    assert resp.status_code == 200
    assert resp.json() == []
