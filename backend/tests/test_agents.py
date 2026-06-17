"""TRA-55 — Agent profile endpoints + represented players list."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.players.models import Player

pytestmark = pytest.mark.asyncio


# ── Helpers ───────────────────────────────────────────────────────────────────


async def _register_agent(client: AsyncClient, email: str) -> dict:
    resp = await client.post("/auth/register", json={
        "email": email, "password": "password123",
        "user_type": "AGENT",
        "display_name": "Test Agent", "agency_name": "Best Agency", "country": "England",
    })
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _register_club(client: AsyncClient, email: str) -> dict:
    resp = await client.post("/auth/register", json={"email": email, "password": "password123"})
    assert resp.status_code == 201, resp.text
    return resp.json()


def _headers(tokens: dict) -> dict:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def _make_player(db: AsyncSession, name: str = "Test Player") -> Player:
    player = Player(name=name, position="FWD")
    db.add(player)
    await db.commit()
    return player


async def _create_mandate(client: AsyncClient, agent_tokens: dict, player_id: str, exclusive: bool = False) -> dict:
    resp = await client.post("/mandates/", json={
        "player_id": player_id, "exclusive": exclusive,
    }, headers=_headers(agent_tokens))
    assert resp.status_code == 201, resp.text
    return resp.json()


# ── Agent profile CRUD ────────────────────────────────────────────────────────


async def test_agent_can_get_own_profile(client: AsyncClient):
    tokens = await _register_agent(client, "agent1@agents-test.com")
    resp = await client.get("/agents/me", headers=_headers(tokens))
    assert resp.status_code == 200
    data = resp.json()
    assert data["display_name"] == "Test Agent"
    assert data["agency_name"] == "Best Agency"
    assert data["country"] == "England"
    assert data["verified"] is False


async def test_agent_can_update_profile(client: AsyncClient):
    tokens = await _register_agent(client, "agent2@agents-test.com")
    resp = await client.patch("/agents/me", json={
        "display_name": "Updated Agent",
        "agency_name": "New Agency",
    }, headers=_headers(tokens))
    assert resp.status_code == 200
    data = resp.json()
    assert data["display_name"] == "Updated Agent"
    assert data["agency_name"] == "New Agency"
    assert data["country"] == "England"  # unchanged


async def test_agent_update_partial_fields(client: AsyncClient):
    tokens = await _register_agent(client, "agent3@agents-test.com")
    resp = await client.patch("/agents/me", json={"country": "Spain"}, headers=_headers(tokens))
    assert resp.status_code == 200
    assert resp.json()["country"] == "Spain"
    assert resp.json()["display_name"] == "Test Agent"  # unchanged


async def test_club_cannot_access_agents_me(client: AsyncClient):
    tokens = await _register_club(client, "club1@agents-test.com")
    resp = await client.get("/agents/me", headers=_headers(tokens))
    assert resp.status_code == 403


async def test_unauthenticated_cannot_access_agents_me(client: AsyncClient):
    resp = await client.get("/agents/me")
    assert resp.status_code == 401


# ── Represented players list ──────────────────────────────────────────────────


async def test_agent_with_no_mandates_sees_empty_list(client: AsyncClient):
    tokens = await _register_agent(client, "agent4@agents-test.com")
    resp = await client.get("/agents/me/players", headers=_headers(tokens))
    assert resp.status_code == 200
    assert resp.json() == []


async def test_agent_sees_represented_player_after_mandate(client: AsyncClient, db: AsyncSession):
    tokens = await _register_agent(client, "agent5@agents-test.com")
    player = await _make_player(db, "Represented Player")
    await _create_mandate(client, tokens, str(player.id))

    resp = await client.get("/agents/me/players", headers=_headers(tokens))
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["player_name"] == "Represented Player"
    assert items[0]["player_id"] == str(player.id)
    assert items[0]["status"] == "ACTIVE"


async def test_agent_sees_multiple_represented_players(client: AsyncClient, db: AsyncSession):
    tokens = await _register_agent(client, "agent6@agents-test.com")
    p1 = await _make_player(db, "Alice")
    p2 = await _make_player(db, "Bob")
    await _create_mandate(client, tokens, str(p1.id))
    await _create_mandate(client, tokens, str(p2.id))

    resp = await client.get("/agents/me/players", headers=_headers(tokens))
    assert resp.status_code == 200
    assert len(resp.json()) == 2


async def test_revoked_mandate_not_in_list(client: AsyncClient, db: AsyncSession):
    tokens = await _register_agent(client, "agent7@agents-test.com")
    player = await _make_player(db)
    mandate = await _create_mandate(client, tokens, str(player.id))

    await client.post(f"/mandates/{mandate['id']}/revoke", headers=_headers(tokens))

    resp = await client.get("/agents/me/players", headers=_headers(tokens))
    assert resp.status_code == 200
    assert resp.json() == []
