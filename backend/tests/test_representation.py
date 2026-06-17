"""TRA-55 — Player representation endpoints (view + revoke)."""

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
        "display_name": "Agent", "agency_name": "Agency", "country": "England",
    })
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _register_club(client: AsyncClient, email: str) -> dict:
    resp = await client.post("/auth/register", json={"email": email, "password": "password123"})
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _register_player(client: AsyncClient, email: str, player_id: str) -> dict:
    resp = await client.post("/auth/register", json={
        "email": email, "password": "password123",
        "user_type": "PLAYER", "player_id": player_id,
    })
    assert resp.status_code == 201, resp.text
    return resp.json()


def _headers(tokens: dict) -> dict:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def _make_player(db: AsyncSession) -> Player:
    player = Player(name="Test Player", position="MID")
    db.add(player)
    await db.commit()
    return player


async def _create_mandate(client: AsyncClient, agent_tokens: dict, player_id: str, exclusive: bool = False) -> dict:
    resp = await client.post("/mandates/", json={
        "player_id": player_id, "exclusive": exclusive,
    }, headers=_headers(agent_tokens))
    assert resp.status_code == 201, resp.text
    return resp.json()


# ── GET /players/{id}/representation ─────────────────────────────────────────


async def test_authenticated_user_can_view_player_representation(client: AsyncClient, db: AsyncSession):
    agent_tokens = await _register_agent(client, "ag1@repr-test.com")
    club_tokens = await _register_club(client, "cl1@repr-test.com")
    player = await _make_player(db)
    await _create_mandate(client, agent_tokens, str(player.id))

    resp = await client.get(f"/players/{player.id}/representation", headers=_headers(club_tokens))
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["player_id"] == str(player.id)
    assert items[0]["status"] == "ACTIVE"


async def test_unauthenticated_cannot_view_representation(client: AsyncClient, db: AsyncSession):
    player = await _make_player(db)
    resp = await client.get(f"/players/{player.id}/representation")
    assert resp.status_code == 401


async def test_player_with_no_mandate_returns_empty(client: AsyncClient, db: AsyncSession):
    club_tokens = await _register_club(client, "cl2@repr-test.com")
    player = await _make_player(db)

    resp = await client.get(f"/players/{player.id}/representation", headers=_headers(club_tokens))
    assert resp.status_code == 200
    assert resp.json() == []


# ── POST /players/{id}/representation/{mid}/revoke ───────────────────────────


async def test_player_can_revoke_their_own_mandate(client: AsyncClient, db: AsyncSession):
    agent_tokens = await _register_agent(client, "ag2@repr-test.com")
    player = await _make_player(db)
    player_tokens = await _register_player(client, "pl1@repr-test.com", str(player.id))

    mandate = await _create_mandate(client, agent_tokens, str(player.id))

    resp = await client.post(
        f"/players/{player.id}/representation/{mandate['id']}/revoke",
        headers=_headers(player_tokens),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "REVOKED"


async def test_player_revoke_clears_exclusive_agent_pointer(client: AsyncClient, db: AsyncSession):
    from sqlalchemy import select
    agent_tokens = await _register_agent(client, "ag3@repr-test.com")
    player = await _make_player(db)
    player_tokens = await _register_player(client, "pl2@repr-test.com", str(player.id))

    mandate = await _create_mandate(client, agent_tokens, str(player.id), exclusive=True)

    await client.post(
        f"/players/{player.id}/representation/{mandate['id']}/revoke",
        headers=_headers(player_tokens),
    )

    result = await db.execute(select(Player).where(Player.id == player.id))
    refreshed = result.scalar_one()
    assert refreshed.agent_id is None


async def test_player_cannot_revoke_another_players_mandate(client: AsyncClient, db: AsyncSession):
    agent_tokens = await _register_agent(client, "ag4@repr-test.com")
    player_a = await _make_player(db)
    player_b = await _make_player(db)
    player_b_tokens = await _register_player(client, "plb@repr-test.com", str(player_b.id))

    mandate = await _create_mandate(client, agent_tokens, str(player_a.id))

    resp = await client.post(
        f"/players/{player_a.id}/representation/{mandate['id']}/revoke",
        headers=_headers(player_b_tokens),
    )
    assert resp.status_code == 403


async def test_club_cannot_revoke_player_mandate(client: AsyncClient, db: AsyncSession):
    agent_tokens = await _register_agent(client, "ag5@repr-test.com")
    club_tokens = await _register_club(client, "cl3@repr-test.com")
    player = await _make_player(db)

    mandate = await _create_mandate(client, agent_tokens, str(player.id))

    resp = await client.post(
        f"/players/{player.id}/representation/{mandate['id']}/revoke",
        headers=_headers(club_tokens),
    )
    assert resp.status_code == 403
