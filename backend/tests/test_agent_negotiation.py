"""TRA-127 — agent negotiation authorization regression tests.

Proves that only the agent actually invited to a deal (via the
AgentDealInvitation created when the deal entered AGENT_NEGOTIATION) can
create that deal's AgentNegotiation record — not just any agent on the
platform who happens to write to it first.
"""

import uuid as _uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.models import AgentDealInvitation
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


def _headers(tokens: dict) -> dict:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def _setup_invited_deal(client: AsyncClient, db: AsyncSession) -> dict:
    """Deal in AGENT_NEGOTIATION with an invitation for one specific agent, and
    no AgentNegotiation record yet — the exact state where TRA-127 lived: the
    first write to the (currently nonexistent) negotiation record is what used
    to be unguarded.
    """
    buyer_tokens = await _register_club(client, "buyer@negterms.com")
    seller_tokens = await _register_club(client, "seller@negterms.com")
    invited_agent_tokens = await _register_agent(client, "invited@negterms.com")

    buyer_id = (await client.get("/clubs/me", headers=_headers(buyer_tokens))).json()["id"]
    seller_id = (await client.get("/clubs/me", headers=_headers(seller_tokens))).json()["id"]
    invited_agent_profile = (await client.get("/agents/me", headers=_headers(invited_agent_tokens))).json()

    player = Player(name="Negotiation Terms Player", position="MID")
    db.add(player)
    await db.commit()

    deal = Deal(
        buyer_club_id=_uuid.UUID(buyer_id),
        seller_club_id=_uuid.UUID(seller_id),
        player_id=player.id,
        agreed_fee=Decimal("8000000"),
        status=DealStatus.IN_PROGRESS,
        stage=DealStage.AGENT_NEGOTIATION,
    )
    db.add(deal)
    await db.flush()

    invitation = AgentDealInvitation(deal_id=deal.id, agent_id=_uuid.UUID(invited_agent_profile["id"]))
    db.add(invitation)
    await db.commit()

    return {
        "deal_id": str(deal.id),
        "buyer": buyer_tokens,
        "invited_agent": invited_agent_tokens,
    }


# ── Tests ─────────────────────────────────────────────────────────────────────


async def test_invited_agent_can_start_negotiation(client: AsyncClient, db: AsyncSession):
    ctx = await _setup_invited_deal(client, db)

    resp = await client.patch(
        f"/deals/{ctx['deal_id']}/agent-negotiation/terms",
        json={"commission_pct": 0.05, "commission_payer": "BUYER"},
        headers=_headers(ctx["invited_agent"]),
    )
    assert resp.status_code == 200, resp.text
    assert Decimal(resp.json()["commission_pct"]) == Decimal("0.05")


async def test_uninvited_agent_cannot_start_negotiation(client: AsyncClient, db: AsyncSession):
    """TRA-127 regression: an agent with no invitation to this deal must not be
    able to insert themselves as its negotiator by writing to it first."""
    ctx = await _setup_invited_deal(client, db)
    rival_agent = await _register_agent(client, "rival@negterms.com")

    resp = await client.patch(
        f"/deals/{ctx['deal_id']}/agent-negotiation/terms",
        json={"commission_pct": 0.10, "commission_payer": "BUYER"},
        headers=_headers(rival_agent),
    )
    assert resp.status_code == 400
    assert "invited" in resp.json()["detail"].lower()


async def test_uninvited_agent_write_does_not_create_a_negotiation_record(
    client: AsyncClient, db: AsyncSession,
):
    """The rejected write must not leave a half-created record behind — the
    invited agent should still see no negotiation exists yet afterwards."""
    ctx = await _setup_invited_deal(client, db)
    rival_agent = await _register_agent(client, "rival-noop@negterms.com")

    await client.patch(
        f"/deals/{ctx['deal_id']}/agent-negotiation/terms",
        json={"commission_pct": 0.10},
        headers=_headers(rival_agent),
    )

    resp = await client.get(
        f"/deals/{ctx['deal_id']}/agent-negotiation", headers=_headers(ctx["invited_agent"]),
    )
    assert resp.status_code == 404


async def test_second_agent_cannot_hijack_existing_negotiation(client: AsyncClient, db: AsyncSession):
    """Once the invited agent has created the negotiation, a different agent
    still cannot take it over on a later write (the pre-existing guard for
    updates — confirmed still correct alongside the new create-time guard)."""
    ctx = await _setup_invited_deal(client, db)

    first = await client.patch(
        f"/deals/{ctx['deal_id']}/agent-negotiation/terms",
        json={"commission_pct": 0.05},
        headers=_headers(ctx["invited_agent"]),
    )
    assert first.status_code == 200, first.text

    rival_agent = await _register_agent(client, "rival2@negterms.com")
    resp = await client.patch(
        f"/deals/{ctx['deal_id']}/agent-negotiation/terms",
        json={"commission_pct": 0.20},
        headers=_headers(rival_agent),
    )
    assert resp.status_code == 400
    assert "mandated" in resp.json()["detail"].lower()


async def test_negotiating_agent_can_view_deal_detail(client: AsyncClient, db: AsyncSession):
    """TRA-137: the agent workspace (TRA-128) reads the deal via GET /deals/{id}
    — it must not 403 an agent legitimately negotiating this deal."""
    ctx = await _setup_invited_deal(client, db)
    await client.patch(
        f"/deals/{ctx['deal_id']}/agent-negotiation/terms",
        json={"commission_pct": 0.05},
        headers=_headers(ctx["invited_agent"]),
    )

    resp = await client.get(f"/deals/{ctx['deal_id']}", headers=_headers(ctx["invited_agent"]))
    assert resp.status_code == 200, resp.text
    assert resp.json()["id"] == ctx["deal_id"]


async def test_uninvited_agent_cannot_view_deal_detail(client: AsyncClient, db: AsyncSession):
    """TRA-137: a non-participant gets 403, not a misleading 404."""
    ctx = await _setup_invited_deal(client, db)
    rival_agent = await _register_agent(client, "rival-view@negterms.com")

    resp = await client.get(f"/deals/{ctx['deal_id']}", headers=_headers(rival_agent))
    assert resp.status_code == 403
