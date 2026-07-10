"""TRA-53 — Mandate model + active-mandate enforcement."""

import uuid
from datetime import date, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.mandates.models import Mandate, MandateStatus
from app.mandates.service import expire_mandates
from app.players.models import Player

pytestmark = pytest.mark.asyncio


# ── Helpers ───────────────────────────────────────────────────────────────────


async def _register_agent(client: AsyncClient, email: str) -> dict:
    resp = await client.post("/auth/register", json={
        "email": email,
        "password": "password123",
        "user_type": "AGENT",
        "display_name": "Test Agent",
        "agency_name": "Test Agency",
        "country": "England",
    })
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _register_club(client: AsyncClient, email: str) -> dict:
    resp = await client.post("/auth/register", json={
        "email": email,
        "password": "password123",
    })
    assert resp.status_code == 201, resp.text
    return resp.json()


def _headers(tokens: dict) -> dict:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def _make_player(db: AsyncSession) -> Player:
    player = Player(name="Test Player", position="FWD")
    db.add(player)
    await db.commit()
    return player


# ── Tests ─────────────────────────────────────────────────────────────────────


async def test_agent_can_create_non_exclusive_mandate(client: AsyncClient, db: AsyncSession):
    tokens = await _register_agent(client, "agent@test.com")
    player = await _make_player(db)

    resp = await client.post("/mandates/", json={
        "player_id": str(player.id),
        "exclusive": False,
    }, headers=_headers(tokens))

    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["player_id"] == str(player.id)
    assert data["status"] == "ACTIVE"
    assert data["exclusive"] is False


async def test_agent_can_create_exclusive_mandate_sets_player_agent_id(
    client: AsyncClient, db: AsyncSession
):
    tokens = await _register_agent(client, "agent2@test.com")
    player = await _make_player(db)

    resp = await client.post("/mandates/", json={
        "player_id": str(player.id),
        "exclusive": True,
    }, headers=_headers(tokens))

    assert resp.status_code == 201, resp.text

    result = await db.execute(select(Player).where(Player.id == player.id))
    refreshed = result.scalar_one()
    assert refreshed.agent_id is not None


async def test_club_user_cannot_create_mandate(client: AsyncClient, db: AsyncSession):
    tokens = await _register_club(client, "club@test.com")
    player = await _make_player(db)

    resp = await client.post("/mandates/", json={
        "player_id": str(player.id),
    }, headers=_headers(tokens))

    assert resp.status_code == 403


async def test_unauthenticated_cannot_create_mandate(client: AsyncClient, db: AsyncSession):
    player = await _make_player(db)
    resp = await client.post("/mandates/", json={"player_id": str(player.id)})
    assert resp.status_code == 401


async def test_second_exclusive_mandate_rejected(client: AsyncClient, db: AsyncSession):
    agent1 = await _register_agent(client, "ag1@test.com")
    agent2 = await _register_agent(client, "ag2@test.com")
    player = await _make_player(db)

    r1 = await client.post("/mandates/", json={
        "player_id": str(player.id), "exclusive": True,
    }, headers=_headers(agent1))
    assert r1.status_code == 201

    r2 = await client.post("/mandates/", json={
        "player_id": str(player.id), "exclusive": True,
    }, headers=_headers(agent2))
    assert r2.status_code == 409
    assert "exclusive" in r2.json()["detail"].lower()


async def test_non_exclusive_mandates_can_coexist(client: AsyncClient, db: AsyncSession):
    agent1 = await _register_agent(client, "ne1@test.com")
    agent2 = await _register_agent(client, "ne2@test.com")
    player = await _make_player(db)

    r1 = await client.post("/mandates/", json={
        "player_id": str(player.id), "exclusive": False,
    }, headers=_headers(agent1))
    r2 = await client.post("/mandates/", json={
        "player_id": str(player.id), "exclusive": False,
    }, headers=_headers(agent2))

    assert r1.status_code == 201
    assert r2.status_code == 201


async def test_revoke_mandate_sets_status_revoked(client: AsyncClient, db: AsyncSession):
    tokens = await _register_agent(client, "rev@test.com")
    player = await _make_player(db)

    create_resp = await client.post("/mandates/", json={
        "player_id": str(player.id), "exclusive": False,
    }, headers=_headers(tokens))
    mandate_id = create_resp.json()["id"]

    revoke_resp = await client.post(
        f"/mandates/{mandate_id}/revoke", headers=_headers(tokens)
    )
    assert revoke_resp.status_code == 200
    assert revoke_resp.json()["status"] == "REVOKED"


async def test_revoke_exclusive_clears_player_agent_id(client: AsyncClient, db: AsyncSession):
    tokens = await _register_agent(client, "excl@test.com")
    player = await _make_player(db)

    create_resp = await client.post("/mandates/", json={
        "player_id": str(player.id), "exclusive": True,
    }, headers=_headers(tokens))
    mandate_id = create_resp.json()["id"]

    await client.post(f"/mandates/{mandate_id}/revoke", headers=_headers(tokens))

    result = await db.execute(select(Player).where(Player.id == player.id))
    refreshed = result.scalar_one()
    assert refreshed.agent_id is None


async def test_agent_cannot_revoke_other_agents_mandate(client: AsyncClient, db: AsyncSession):
    agent1 = await _register_agent(client, "own@test.com")
    agent2 = await _register_agent(client, "other@test.com")
    player = await _make_player(db)

    create_resp = await client.post("/mandates/", json={
        "player_id": str(player.id), "exclusive": False,
    }, headers=_headers(agent1))
    mandate_id = create_resp.json()["id"]

    resp = await client.post(
        f"/mandates/{mandate_id}/revoke", headers=_headers(agent2)
    )
    assert resp.status_code == 403


# ── Item 11: mandate expiry ──────────────────────────────────────────────────


async def test_expire_mandates_flips_status_and_clears_agent_id(
    client: AsyncClient, db: AsyncSession
):
    tokens = await _register_agent(client, "lapsed@test.com")
    player = await _make_player(db)

    create_resp = await client.post("/mandates/", json={
        "player_id": str(player.id), "exclusive": True,
    }, headers=_headers(tokens))
    mandate_id = uuid.UUID(create_resp.json()["id"])

    mandate = await db.get(Mandate, mandate_id)
    mandate.end_date = date.today() - timedelta(days=1)
    await db.commit()

    count = await expire_mandates(db)
    await db.commit()
    assert count == 1

    refreshed_mandate = await db.get(Mandate, mandate_id)
    assert refreshed_mandate.status == MandateStatus.EXPIRED

    result = await db.execute(select(Player).where(Player.id == player.id))
    refreshed_player = result.scalar_one()
    assert refreshed_player.agent_id is None


async def test_expire_mandates_ignores_future_end_date(client: AsyncClient, db: AsyncSession):
    tokens = await _register_agent(client, "future@test.com")
    player = await _make_player(db)

    create_resp = await client.post("/mandates/", json={
        "player_id": str(player.id), "exclusive": False,
    }, headers=_headers(tokens))
    mandate_id = uuid.UUID(create_resp.json()["id"])

    mandate = await db.get(Mandate, mandate_id)
    mandate.end_date = date.today() + timedelta(days=30)
    await db.commit()

    count = await expire_mandates(db)
    assert count == 0

    refreshed = await db.get(Mandate, mandate_id)
    assert refreshed.status == MandateStatus.ACTIVE


async def test_expire_mandates_ignores_no_end_date(client: AsyncClient, db: AsyncSession):
    tokens = await _register_agent(client, "noend@test.com")
    player = await _make_player(db)

    await client.post("/mandates/", json={
        "player_id": str(player.id), "exclusive": False,
    }, headers=_headers(tokens))

    count = await expire_mandates(db)
    assert count == 0
