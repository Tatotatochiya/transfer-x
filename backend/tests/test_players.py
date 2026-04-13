"""Player endpoint tests — M2."""

import pytest
from httpx import AsyncClient

from tests.conftest import _auth_headers, _register

pytestmark = pytest.mark.asyncio


# ── Helpers ───────────────────────────────────────────────────────────────────


async def _create_player(client, headers, name="Ronaldo", position="FWD") -> dict:
    resp = await client.post(
        "/players", json={"name": name, "age": 25, "position": position}, headers=headers
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# ── Create player ─────────────────────────────────────────────────────────────


async def test_create_player(client: AsyncClient, auth_headers: dict):
    data = await _create_player(client, auth_headers)
    assert data["name"] == "Ronaldo"
    assert data["position"] == "FWD"
    assert data["status"] == "FREE_AGENT"
    assert data["open_to_offers"] is False


async def test_create_player_requires_auth(client: AsyncClient):
    resp = await client.post("/players", json={"name": "Ghost"})
    assert resp.status_code == 401


async def test_create_player_invalid_position(client: AsyncClient, auth_headers: dict):
    resp = await client.post(
        "/players", json={"name": "X", "position": "STRIKER"}, headers=auth_headers
    )
    assert resp.status_code == 422


# ── List own players ──────────────────────────────────────────────────────────


async def test_list_own_players(client: AsyncClient, auth_headers: dict):
    await _create_player(client, auth_headers, "Player A")
    await _create_player(client, auth_headers, "Player B")
    resp = await client.get("/players", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    names = {p["name"] for p in data["items"]}
    assert "Player A" in names and "Player B" in names


async def test_other_user_cannot_see_my_players(client: AsyncClient, auth_headers: dict):
    await _create_player(client, auth_headers, "Secret Player")
    other_tokens = await _register(client, "other@test.com")
    resp = await client.get("/players", headers=_auth_headers(other_tokens))
    assert resp.json()["total"] == 0


# ── Update player ─────────────────────────────────────────────────────────────


async def test_update_player(client: AsyncClient, auth_headers: dict):
    player = await _create_player(client, auth_headers)
    resp = await client.patch(
        f"/players/{player['id']}",
        json={"name": "Messi", "age": 36},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Messi"
    assert resp.json()["age"] == 36


async def test_update_other_users_player_is_404(client: AsyncClient, auth_headers: dict):
    player = await _create_player(client, auth_headers)
    other_tokens = await _register(client, "other2@test.com")
    resp = await client.patch(
        f"/players/{player['id']}",
        json={"name": "Hacker"},
        headers=_auth_headers(other_tokens),
    )
    assert resp.status_code == 404


# ── Market browse ─────────────────────────────────────────────────────────────


async def test_market_shows_public_players(client: AsyncClient, auth_headers: dict):
    await _create_player(client, auth_headers, "Public Star")
    resp = await client.get("/players/market")  # no auth
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1


async def test_market_hides_clubs_only_from_anon(client: AsyncClient, auth_headers: dict):
    resp = await client.post(
        "/players",
        json={"name": "Clubs Only", "visibility": "CLUBS_ONLY"},
        headers=auth_headers,
    )
    player_id = resp.json()["id"]

    anon_resp = await client.get("/players/market")
    ids = [p["id"] for p in anon_resp.json()["items"]]
    assert player_id not in ids

    auth_resp = await client.get("/players/market", headers=auth_headers)
    ids = [p["id"] for p in auth_resp.json()["items"]]
    assert player_id in ids


async def test_market_filter_by_position(client: AsyncClient, auth_headers: dict):
    await _create_player(client, auth_headers, "GK Guy", position="GK")
    await _create_player(client, auth_headers, "FWD Guy", position="FWD")
    resp = await client.get("/players/market?position=GK", headers=auth_headers)
    for p in resp.json()["items"]:
        assert p["position"] == "GK"


async def test_market_detail(client: AsyncClient, auth_headers: dict):
    player = await _create_player(client, auth_headers)
    resp = await client.get(f"/players/market/{player['id']}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["name"] == "Ronaldo"


async def test_market_detail_private_hidden_from_others(client: AsyncClient, auth_headers: dict):
    resp = await client.post(
        "/players", json={"name": "Private", "visibility": "PRIVATE"}, headers=auth_headers
    )
    player_id = resp.json()["id"]
    other_tokens = await _register(client, "voyeur@test.com")
    resp = await client.get(
        f"/players/market/{player_id}", headers=_auth_headers(other_tokens)
    )
    assert resp.status_code == 404


# ── Contracts ─────────────────────────────────────────────────────────────────


async def test_add_contract_normalizes_status(client: AsyncClient, auth_headers: dict):
    player = await _create_player(client, auth_headers)
    assert player["status"] == "FREE_AGENT"

    # Get the owning club's ID
    my_club = (await client.get("/clubs/me", headers=auth_headers)).json()
    club_id = my_club["id"]

    resp = await client.post(
        f"/players/{player['id']}/contracts",
        json={"club_id": club_id, "wage_weekly": "50000.00"},
        headers=auth_headers,
    )
    assert resp.status_code == 201

    # Player should now be CONTRACTED
    detail = await client.get(f"/players/market/{player['id']}", headers=auth_headers)
    assert detail.json()["status"] == "CONTRACTED"
    assert detail.json()["active_contract"] is not None
    assert float(detail.json()["active_contract"]["wage_weekly"]) == 50000.0


async def test_add_contract_replaces_existing(client: AsyncClient, auth_headers: dict):
    player = await _create_player(client, auth_headers)
    my_club = (await client.get("/clubs/me", headers=auth_headers)).json()
    club_id = my_club["id"]

    await client.post(
        f"/players/{player['id']}/contracts",
        json={"club_id": club_id, "wage_weekly": "30000"},
        headers=auth_headers,
    )
    # Second contract replaces the first
    await client.post(
        f"/players/{player['id']}/contracts",
        json={"club_id": club_id, "wage_weekly": "60000"},
        headers=auth_headers,
    )
    detail = (await client.get(f"/players/market/{player['id']}", headers=auth_headers)).json()
    assert float(detail["active_contract"]["wage_weekly"]) == 60000.0


async def test_deactivate_contract_makes_free_agent(client: AsyncClient, auth_headers: dict):
    player = await _create_player(client, auth_headers)
    my_club = (await client.get("/clubs/me", headers=auth_headers)).json()

    contract = (
        await client.post(
            f"/players/{player['id']}/contracts",
            json={"club_id": my_club["id"]},
            headers=auth_headers,
        )
    ).json()

    assert contract["is_active"] is True

    resp = await client.delete(
        f"/players/{player['id']}/contracts/{contract['id']}", headers=auth_headers
    )
    assert resp.status_code == 204

    detail = (await client.get(f"/players/market/{player['id']}", headers=auth_headers)).json()
    assert detail["status"] == "FREE_AGENT"
    assert detail["active_contract"] is None


async def test_deactivate_already_inactive_contract(client: AsyncClient, auth_headers: dict):
    player = await _create_player(client, auth_headers)
    my_club = (await client.get("/clubs/me", headers=auth_headers)).json()

    contract = (
        await client.post(
            f"/players/{player['id']}/contracts",
            json={"club_id": my_club["id"]},
            headers=auth_headers,
        )
    ).json()

    await client.delete(
        f"/players/{player['id']}/contracts/{contract['id']}", headers=auth_headers
    )
    # Second deactivate should 400
    resp = await client.delete(
        f"/players/{player['id']}/contracts/{contract['id']}", headers=auth_headers
    )
    assert resp.status_code == 400
