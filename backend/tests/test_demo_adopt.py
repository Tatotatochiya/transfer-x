"""Adopting a deal into a demo (demo/service.adopt_deal): the house plays its
agent and player, and Reset puts the deal back as it was."""
import uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import settings
from tests.test_agent_negotiation import _headers, _register_club, _setup_invited_deal

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def demo_on(monkeypatch):
    monkeypatch.setattr(settings, "demo_enabled", True)


async def _tick(db_engine) -> int:
    from app.demo.house import tick

    return await tick(async_sessionmaker(db_engine, expire_on_commit=False))


async def test_a_stuck_deal_is_adopted_played_and_put_back(client: AsyncClient, db: AsyncSession, db_engine):
    from app.agents.models import AgentNegotiation
    from app.auth.models import User
    from app.deals.models import TermProposal

    ctx = await _setup_invited_deal(client, db)  # a seeded-style deal, waiting on the agent
    deal, buyer = ctx["deal_id"], _headers(ctx["buyer"])
    await db.execute(update(User).where(User.email == "buyer@negterms.com").values(can_demo=True))
    await db.execute(update(User).where(User.email == "invited@negterms.com").values(last_active_at=None))
    await db.commit()

    # Outside a demo nothing plays the agent, and there's nothing to adopt into.
    assert await _tick(db_engine) == 0
    assert (await client.get(f"/demo/deals/{deal}", headers=buyer)).json() == {
        "in_demo": False, "can_adopt": False, "adopt_reason": None}

    assert (await client.post("/demo/run", headers=buyer)).status_code == 201
    assert (await client.get(f"/demo/deals/{deal}", headers=buyer)).json()["can_adopt"] is True
    # A club that isn't party to it can't adopt it.
    outsider = await _register_club(client, "outsider@negterms.com")
    await db.execute(update(User).where(User.email == "outsider@negterms.com").values(can_demo=True))
    await db.commit()
    await client.post("/demo/run", headers=_headers(outsider))
    assert (await client.post(f"/demo/deals/{deal}/adopt", headers=_headers(outsider))).status_code == 409

    r = await client.post(f"/demo/deals/{deal}/adopt", headers=buyer)
    assert r.status_code == 200, r.text
    assert (await client.get(f"/demo/deals/{deal}", headers=buyer)).json()["in_demo"] is True
    assert (await client.post(f"/demo/deals/{deal}/adopt", headers=buyer)).status_code == 409  # once

    # The house plays the agent: he proposes, and answers the tester's counter.
    assert await _tick(db_engine) == 1
    r = await client.post(f"/deals/{deal}/agent-negotiation/club-counter", headers=buyer,
                          json={"commission_pct": 0.02, "commission_payer": "BUYER"})
    assert r.status_code == 200, r.text
    assert await _tick(db_engine) == 1
    db.expire_all()
    neg = (await db.execute(select(AgentNegotiation).where(AgentNegotiation.deal_id == uuid.UUID(deal)))).scalar_one()
    assert (neg.proposed_by, neg.commission_pct) == ("AGENT", Decimal("0.035"))

    # Reset: the deal is as it was when adopted.
    report = (await client.post("/demo/run/reset", headers=buyer)).json()
    assert report["skipped"] == [], report
    db.expire_all()
    assert (await db.execute(select(AgentNegotiation).where(AgentNegotiation.deal_id == uuid.UUID(deal)))).first() is None
    assert (await db.execute(select(TermProposal).where(TermProposal.deal_id == uuid.UUID(deal)))).first() is None
    body = (await client.get(f"/deals/{deal}", headers=buyer)).json()
    assert (body["status"], body["stage"]) == ("IN_PROGRESS", "AGENT_NEGOTIATION")
    assert await _tick(db_engine) == 0  # no longer in a demo: nobody plays the agent


async def test_an_adopted_deal_can_be_forced_and_a_reminder_moves_it(client: AsyncClient, db: AsyncSession, db_engine):
    from app.auth.models import User

    ctx = await _setup_invited_deal(client, db)
    deal, buyer = ctx["deal_id"], _headers(ctx["buyer"])
    from datetime import datetime, timezone

    await db.execute(update(User).where(User.email == "buyer@negterms.com").values(can_demo=True))
    # Someone is signed in as the agent: the house leaves him be, unless the tester insists.
    await db.execute(update(User).where(User.email == "invited@negterms.com").values(last_active_at=datetime.now(timezone.utc)))
    await db.commit()
    await client.post("/demo/run", headers=buyer)
    await client.post(f"/demo/deals/{deal}/adopt", headers=buyer)
    assert await _tick(db_engine) == 0

    r = await client.post(f"/demo/deals/{deal}/make", headers=buyer)
    assert r.status_code == 200 and r.json() == {"done": "agent_terms"}, r.text
    # Now the club's move; reminders go straight away in a demo.
    state = (await client.get(f"/reminders/deal/{deal}", headers=buyer)).json()
    assert state["reason"] == "It's your move."
