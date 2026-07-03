"""TRA-136 — scoped negotiation messaging isolation tests.

Proves that:
  - The mandated agent can read/write both CLUB_SIDE and PLAYER_SIDE.
  - A club party can never read or post PLAYER_SIDE messages.
  - The player can never read or post CLUB_SIDE messages.
  - A club that isn't a party to the deal, and an agent who isn't the
    mandated one, are rejected outright.
"""

from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.models import AgentNegotiation
from app.deals.models import Deal, DealStage, DealStatus
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


async def _setup_negotiation(client: AsyncClient, db: AsyncSession):
    """Buyer club + seller club + agent (mandated) + player, deal in AGENT_NEGOTIATION."""
    buyer_tokens = await _register_club(client, "buyer@negtest.com")
    seller_tokens = await _register_club(client, "seller@negtest.com")
    agent_tokens = await _register_agent(client, "agent@negtest.com")

    buyer_id = (await client.get("/clubs/me", headers=_headers(buyer_tokens))).json()["id"]
    seller_id = (await client.get("/clubs/me", headers=_headers(seller_tokens))).json()["id"]
    agent_profile = (await client.get("/agents/me", headers=_headers(agent_tokens))).json()

    player = Player(name="Negotiation Test Player", position="FWD")
    db.add(player)
    await db.commit()

    player_tokens = await _register_player(client, "player@negtest.com", str(player.id))

    import uuid as _uuid
    deal = Deal(
        buyer_club_id=_uuid.UUID(buyer_id),
        seller_club_id=_uuid.UUID(seller_id),
        player_id=player.id,
        agreed_fee=Decimal("10000000"),
        status=DealStatus.IN_PROGRESS,
        stage=DealStage.AGENT_NEGOTIATION,
    )
    db.add(deal)
    await db.flush()

    negotiation = AgentNegotiation(deal_id=deal.id, agent_id=_uuid.UUID(agent_profile["id"]))
    db.add(negotiation)
    await db.commit()

    return {
        "buyer": buyer_tokens,
        "seller": seller_tokens,
        "agent": agent_tokens,
        "player": player_tokens,
        "negotiation_id": str(negotiation.id),
    }


# ── Agent: full access ────────────────────────────────────────────────────────


async def test_agent_can_post_and_read_both_threads(client: AsyncClient, db: AsyncSession):
    ctx = await _setup_negotiation(client, db)
    neg_id = ctx["negotiation_id"]

    club_msg = await client.post(
        f"/negotiations/{neg_id}/messages",
        json={"thread": "CLUB_SIDE", "body": "Commission proposal: 5%"},
        headers=_headers(ctx["agent"]),
    )
    assert club_msg.status_code == 201, club_msg.text

    player_msg = await client.post(
        f"/negotiations/{neg_id}/messages",
        json={"thread": "PLAYER_SIDE", "body": "Wage proposal: £150k/week"},
        headers=_headers(ctx["agent"]),
    )
    assert player_msg.status_code == 201, player_msg.text

    resp = await client.get(f"/negotiations/{neg_id}/messages", headers=_headers(ctx["agent"]))
    assert resp.status_code == 200
    threads = {m["thread"] for m in resp.json()}
    assert threads == {"CLUB_SIDE", "PLAYER_SIDE"}


# ── Club isolation ────────────────────────────────────────────────────────────


async def test_club_cannot_read_player_side(client: AsyncClient, db: AsyncSession):
    ctx = await _setup_negotiation(client, db)
    neg_id = ctx["negotiation_id"]

    await client.post(
        f"/negotiations/{neg_id}/messages",
        json={"thread": "PLAYER_SIDE", "body": "Confidential wage discussion"},
        headers=_headers(ctx["agent"]),
    )

    resp = await client.get(
        f"/negotiations/{neg_id}/messages", params={"thread": "PLAYER_SIDE"}, headers=_headers(ctx["buyer"])
    )
    assert resp.status_code == 403


async def test_club_default_fetch_never_includes_player_side(client: AsyncClient, db: AsyncSession):
    """Omitting `thread` must never leak the other side by accident."""
    ctx = await _setup_negotiation(client, db)
    neg_id = ctx["negotiation_id"]

    await client.post(
        f"/negotiations/{neg_id}/messages",
        json={"thread": "PLAYER_SIDE", "body": "Confidential wage discussion"},
        headers=_headers(ctx["agent"]),
    )
    await client.post(
        f"/negotiations/{neg_id}/messages",
        json={"thread": "CLUB_SIDE", "body": "Commission proposal"},
        headers=_headers(ctx["agent"]),
    )

    resp = await client.get(f"/negotiations/{neg_id}/messages", headers=_headers(ctx["buyer"]))
    assert resp.status_code == 200
    bodies = [m["body"] for m in resp.json()]
    assert "Confidential wage discussion" not in bodies
    assert "Commission proposal" in bodies


async def test_club_cannot_post_to_player_side(client: AsyncClient, db: AsyncSession):
    ctx = await _setup_negotiation(client, db)
    neg_id = ctx["negotiation_id"]

    resp = await client.post(
        f"/negotiations/{neg_id}/messages",
        json={"thread": "PLAYER_SIDE", "body": "Trying to sneak into player thread"},
        headers=_headers(ctx["buyer"]),
    )
    assert resp.status_code == 403


async def test_seller_club_is_also_a_club_side_party(client: AsyncClient, db: AsyncSession):
    ctx = await _setup_negotiation(client, db)
    neg_id = ctx["negotiation_id"]

    resp = await client.post(
        f"/negotiations/{neg_id}/messages",
        json={"thread": "CLUB_SIDE", "body": "Seller checking in"},
        headers=_headers(ctx["seller"]),
    )
    assert resp.status_code == 201, resp.text


async def test_non_party_club_rejected_entirely(client: AsyncClient, db: AsyncSession):
    ctx = await _setup_negotiation(client, db)
    neg_id = ctx["negotiation_id"]
    outsider = await _register_club(client, "outsider@negtest.com")

    resp = await client.get(f"/negotiations/{neg_id}/messages", headers=_headers(outsider))
    assert resp.status_code == 403


# ── Player isolation ──────────────────────────────────────────────────────────


async def test_player_cannot_read_club_side(client: AsyncClient, db: AsyncSession):
    ctx = await _setup_negotiation(client, db)
    neg_id = ctx["negotiation_id"]

    await client.post(
        f"/negotiations/{neg_id}/messages",
        json={"thread": "CLUB_SIDE", "body": "Commission talk"},
        headers=_headers(ctx["agent"]),
    )

    resp = await client.get(
        f"/negotiations/{neg_id}/messages", params={"thread": "CLUB_SIDE"}, headers=_headers(ctx["player"])
    )
    assert resp.status_code == 403


async def test_player_cannot_post_to_club_side(client: AsyncClient, db: AsyncSession):
    ctx = await _setup_negotiation(client, db)
    neg_id = ctx["negotiation_id"]

    resp = await client.post(
        f"/negotiations/{neg_id}/messages",
        json={"thread": "CLUB_SIDE", "body": "Trying to sneak into club thread"},
        headers=_headers(ctx["player"]),
    )
    assert resp.status_code == 403


async def test_player_can_post_and_read_own_side(client: AsyncClient, db: AsyncSession):
    ctx = await _setup_negotiation(client, db)
    neg_id = ctx["negotiation_id"]

    resp = await client.post(
        f"/negotiations/{neg_id}/messages",
        json={"thread": "PLAYER_SIDE", "body": "I'd like a signing bonus"},
        headers=_headers(ctx["player"]),
    )
    assert resp.status_code == 201, resp.text

    resp = await client.get(f"/negotiations/{neg_id}/messages", headers=_headers(ctx["player"]))
    assert resp.status_code == 200
    assert all(m["thread"] == "PLAYER_SIDE" for m in resp.json())


# ── Unmandated agent ──────────────────────────────────────────────────────────


async def test_unmandated_agent_rejected(client: AsyncClient, db: AsyncSession):
    ctx = await _setup_negotiation(client, db)
    neg_id = ctx["negotiation_id"]
    other_agent = await _register_agent(client, "other-agent@negtest.com")

    resp = await client.get(f"/negotiations/{neg_id}/messages", headers=_headers(other_agent))
    assert resp.status_code == 403
