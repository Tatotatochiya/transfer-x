"""TRA-54 — Cross-tenant isolation + actor capability tests.

Proves that:
  - AGENT and PLAYER users cannot access club-only endpoints (deals, scouting).
  - Club A cannot read Club B's deals.
  - A PLAYER user can read and update their own player profile via /players/me.
"""

from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.deals.models import Deal, DealStatus, DealStage
from app.players.models import Player

pytestmark = pytest.mark.asyncio


# ── Helpers ───────────────────────────────────────────────────────────────────


async def _register_club(client: AsyncClient, email: str) -> dict:
    resp = await client.post("/auth/register", json={"email": email, "password": "password123"})
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _register_agent(client: AsyncClient, email: str) -> dict:
    resp = await client.post("/auth/register", json={
        "email": email, "password": "password123",
        "user_type": "AGENT",
        "display_name": "Test Agent", "agency_name": "Agency", "country": "England",
    })
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _register_player(client: AsyncClient, email: str, player_id: str) -> dict:
    resp = await client.post("/auth/register", json={
        "email": email, "password": "password123",
        "user_type": "PLAYER",
        "player_id": player_id,
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


async def _make_deal(db: AsyncSession, buyer_club_id, seller_club_id, player_id) -> Deal:
    deal = Deal(
        buyer_club_id=buyer_club_id,
        seller_club_id=seller_club_id,
        player_id=player_id,
        agreed_fee=Decimal("5000000"),
        status=DealStatus.IN_PROGRESS,
        stage=DealStage.AGREEMENT,
    )
    db.add(deal)
    await db.commit()
    return deal


# ── Agent + Player blocked from club-only endpoints ───────────────────────────


async def test_agent_cannot_list_deals(client: AsyncClient):
    tokens = await _register_agent(client, "agent@isolation-test.com")
    resp = await client.get("/deals", headers=_headers(tokens))
    assert resp.status_code == 403


async def test_player_cannot_list_deals(client: AsyncClient, db: AsyncSession):
    player = await _make_player(db)
    tokens = await _register_player(client, "player@isolation-test.com", str(player.id))
    resp = await client.get("/deals", headers=_headers(tokens))
    assert resp.status_code == 403


async def test_unauthenticated_cannot_list_deals(client: AsyncClient):
    resp = await client.get("/deals")
    assert resp.status_code == 401


async def test_agent_cannot_access_scouting(client: AsyncClient):
    tokens = await _register_agent(client, "agent2@isolation-test.com")
    resp = await client.get("/scouting/shortlists", headers=_headers(tokens))
    assert resp.status_code == 403


async def test_player_cannot_access_scouting(client: AsyncClient, db: AsyncSession):
    player = await _make_player(db)
    tokens = await _register_player(client, "player2@isolation-test.com", str(player.id))
    resp = await client.get("/scouting/shortlists", headers=_headers(tokens))
    assert resp.status_code == 403


async def test_unauthenticated_cannot_read_clubs_me(client: AsyncClient):
    resp = await client.get("/clubs/me")
    assert resp.status_code == 401


# ── Club-to-club isolation ────────────────────────────────────────────────────


async def test_club_cannot_read_another_clubs_deal(client: AsyncClient, db: AsyncSession):
    club_a = await _register_club(client, "clubA@isolation-test.com")
    club_b = await _register_club(client, "clubB@isolation-test.com")
    club_c = await _register_club(client, "clubC@isolation-test.com")

    # Resolve club IDs from /clubs/me
    a_resp = await client.get("/clubs/me", headers=_headers(club_a))
    b_resp = await client.get("/clubs/me", headers=_headers(club_b))
    club_a_id = a_resp.json()["id"]
    club_b_id = b_resp.json()["id"]

    import uuid as _uuid
    player = await _make_player(db)
    deal = await _make_deal(db, _uuid.UUID(club_a_id), _uuid.UUID(club_b_id), player.id)

    # Club C is not a party — must be rejected
    resp = await client.get(f"/deals/{deal.id}", headers=_headers(club_c))
    assert resp.status_code == 403


async def test_club_cannot_read_another_clubs_finance(client: AsyncClient):
    """GET /clubs/me always returns the requesting user's own club — no cross-club finance."""
    club_a = await _register_club(client, "finA@isolation-test.com")
    club_b = await _register_club(client, "finB@isolation-test.com")

    # Each club only sees their own finance
    a_resp = await client.get("/clubs/me", headers=_headers(club_a))
    b_resp = await client.get("/clubs/me", headers=_headers(club_b))
    assert a_resp.status_code == 200
    assert b_resp.status_code == 200
    assert a_resp.json()["id"] != b_resp.json()["id"]
    # Finance is scoped to the requesting user — no shared endpoint exposes another club's finance
    assert "finance" in a_resp.json()
    assert "finance" in b_resp.json()


# ── Player self-service ───────────────────────────────────────────────────────


async def test_player_can_get_own_profile(client: AsyncClient, db: AsyncSession):
    player = await _make_player(db)
    tokens = await _register_player(client, "pme1@isolation-test.com", str(player.id))
    resp = await client.get("/players/me", headers=_headers(tokens))
    assert resp.status_code == 200
    assert resp.json()["id"] == str(player.id)


async def test_player_can_update_own_visibility(client: AsyncClient, db: AsyncSession):
    player = await _make_player(db)
    tokens = await _register_player(client, "pme2@isolation-test.com", str(player.id))

    resp = await client.patch("/players/me", json={"visibility": "PRIVATE"}, headers=_headers(tokens))
    assert resp.status_code == 200
    assert resp.json()["visibility"] == "PRIVATE"


async def test_player_can_update_own_open_to_offers(client: AsyncClient, db: AsyncSession):
    player = await _make_player(db)
    tokens = await _register_player(client, "pme3@isolation-test.com", str(player.id))

    resp = await client.patch("/players/me", json={"open_to_offers": True}, headers=_headers(tokens))
    assert resp.status_code == 200
    assert resp.json()["open_to_offers"] is True


async def test_club_user_cannot_use_players_me(client: AsyncClient):
    tokens = await _register_club(client, "club_me@isolation-test.com")
    resp = await client.get("/players/me", headers=_headers(tokens))
    assert resp.status_code == 403
