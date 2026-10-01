"""The player's agent on a deal, and the agent-stage next steps.

The deal names the agent representing the player at every stage, and the
next steps at the agent negotiation stage follow the negotiation: the agent
proposes, then the buying club answers, then either club moves it on.
"""

from types import SimpleNamespace

import pytest
from httpx import AsyncClient

from app.ai.assist import deal_steps
from tests.test_agent_negotiation import _headers, _setup_invited_deal


@pytest.mark.asyncio
async def test_deal_names_the_invited_agent(client: AsyncClient, db):
    ctx = await _setup_invited_deal(client, db)
    resp = await client.get(f"/deals/{ctx['deal_id']}", headers=_headers(ctx["buyer"]))
    assert resp.status_code == 200, resp.text
    agent = resp.json()["agent"]
    assert agent["display_name"] == "Test Agent" and agent["agency_name"] == "Agency"


@pytest.mark.asyncio
async def test_agent_stage_steps_follow_the_negotiation(client: AsyncClient, db):
    ctx = await _setup_invited_deal(client, db)
    url = f"/ai/deals/{ctx['deal_id']}/next-steps"

    async def steps():
        resp = await client.get(url, headers=_headers(ctx["buyer"]))
        assert resp.status_code == 200, resp.text
        return [(s["label"], s["owner"]) for s in resp.json()["steps"]]

    # Invited, nothing proposed: the agent's move.
    assert await steps() == [("Propose the commission terms", "agent")]

    resp = await client.patch(
        f"/deals/{ctx['deal_id']}/agent-negotiation/terms",
        json={"commission_pct": 0.05, "commission_payer": "BUYER"}, headers=_headers(ctx["invited_agent"]),
    )
    assert resp.status_code == 200, resp.text
    assert await steps() == [("Answer the agent's commission proposal", "you")]

    resp = await client.post(
        f"/deals/{ctx['deal_id']}/agent-negotiation/club-respond",
        json={"agreement": "AGREED"}, headers=_headers(ctx["buyer"]),
    )
    assert resp.status_code == 200, resp.text
    assert await steps() == [("Move the deal on to personal terms", "either")]


def test_agent_stage_without_a_negotiation_is_the_buyers_as_before():
    import uuid

    from app.deals.models import DealStage, DealStatus

    buyer = uuid.uuid4()
    deal = SimpleNamespace(status=DealStatus.IN_PROGRESS, stage=DealStage.AGENT_NEGOTIATION,
                           buyer_club_id=buyer, seller_club_id=uuid.uuid4())
    assert deal_steps(deal, buyer) == [{"label": "Agree the agent's commission", "owner": "you"}]
