"""Counters on the agent's commission and on personal terms (product ADR 0012)."""
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.test_agent_negotiation import (
    _advance_to_personal_terms, _headers, _register_player_account, _setup_invited_deal,
)

pytestmark = pytest.mark.asyncio


async def _propose(client, ctx, pct=0.08):
    r = await client.patch(f"/deals/{ctx['deal_id']}/agent-negotiation/terms",
                           json={"commission_pct": pct, "commission_payer": "BUYER"}, headers=_headers(ctx["invited_agent"]))
    assert r.status_code == 200, r.text
    return r.json()


async def test_the_club_counters_the_commission_and_the_agent_accepts(client: AsyncClient, db: AsyncSession):
    ctx = await _setup_invited_deal(client, db)
    deal = ctx["deal_id"]
    assert (await _propose(client, ctx))["proposed_by"] == "AGENT"

    # Only the buying club counters, and only once the agent has asked.
    r = await client.post(f"/deals/{deal}/agent-negotiation/club-counter", headers=_headers(ctx["seller"]),
                          json={"commission_pct": 0.04, "commission_payer": "BUYER"})
    assert r.status_code == 400
    r = await client.post(f"/deals/{deal}/agent-negotiation/club-counter", headers=_headers(ctx["buyer"]),
                          json={"commission_pct": 0.04, "commission_payer": "PLAYER", "note": "Our limit"})
    assert r.status_code == 200, r.text
    neg = r.json()
    assert (neg["proposed_by"], neg["club_agreement"], neg["commission_payer"]) == ("BUYER", "PENDING", "PLAYER")
    assert Decimal(neg["commission_amount"]) == Decimal("320000.00")  # 4% of £8m, recalculated

    # The club can't accept its own counter, nor move on before the agent answers.
    r = await client.post(f"/deals/{deal}/agent-negotiation/club-respond", headers=_headers(ctx["buyer"]),
                          json={"agreement": "AGREED"})
    assert r.status_code == 400 and "the agent answers it" in r.json()["detail"]
    assert (await client.post(f"/deals/{deal}/advance", headers=_headers(ctx["buyer"]))).status_code == 400

    r = await client.post(f"/deals/{deal}/agent-negotiation/agent-accept", headers=_headers(ctx["invited_agent"]))
    assert r.status_code == 200 and r.json()["club_agreement"] == "AGREED", r.text
    r = await client.post(f"/deals/{deal}/advance", headers=_headers(ctx["buyer"]))
    assert r.status_code == 200 and r.json()["stage"] == "PERSONAL_TERMS", r.text
    assert Decimal(r.json()["agent_commission_pct"]) == Decimal("0.04")

    # Both sides see the rounds; the selling club doesn't see the commission's.
    rounds = (await client.get(f"/deals/{deal}/term-proposals", headers=_headers(ctx["buyer"]))).json()
    assert [(x["kind"], x["side"], x["note"]) for x in rounds] == [
        ("COMMISSION", "AGENT", None), ("COMMISSION", "BUYER", "Our limit")]
    assert (await client.get(f"/deals/{deal}/term-proposals", headers=_headers(ctx["seller"]))).json() == []


async def test_the_agent_answers_a_counter_with_a_new_proposal(client: AsyncClient, db: AsyncSession):
    ctx = await _setup_invited_deal(client, db)
    await _propose(client, ctx)
    await client.post(f"/deals/{ctx['deal_id']}/agent-negotiation/club-counter", headers=_headers(ctx["buyer"]),
                      json={"commission_pct": 0.04, "commission_payer": "BUYER"})
    again = await _propose(client, ctx, pct=0.06)
    assert (again["proposed_by"], again["club_agreement"]) == ("AGENT", "PENDING")
    assert Decimal(again["commission_amount"]) == Decimal("480000.00")
    # Nothing left for the agent to accept: it's the club's move again.
    r = await client.post(f"/deals/{ctx['deal_id']}/agent-negotiation/agent-accept", headers=_headers(ctx["invited_agent"]))
    assert r.status_code == 400


async def test_declining_the_commission_ends_the_transfer_with_the_reason(client: AsyncClient, db: AsyncSession):
    ctx = await _setup_invited_deal(client, db)
    await _propose(client, ctx)
    r = await client.post(f"/deals/{ctx['deal_id']}/agent-negotiation/club-respond", headers=_headers(ctx["buyer"]),
                          json={"agreement": "DECLINED", "reason": "Too far apart on the fee"})
    assert r.status_code == 200, r.text
    deal = (await client.get(f"/deals/{ctx['deal_id']}", headers=_headers(ctx["buyer"]))).json()
    assert deal["status"] == "COLLAPSED" and deal["collapse_reason"] == "Too far apart on the fee"


async def test_personal_terms_go_back_and_forth_until_one_side_agrees(client: AsyncClient, db: AsyncSession):
    ctx = await _setup_invited_deal(client, db)
    player = await _register_player_account(client, "counter-player@negterms.com", ctx["player_id"])
    await _advance_to_personal_terms(client, ctx)
    deal = ctx["deal_id"]

    # The player can't open: the club or his agent proposes first.
    r = await client.put(f"/deals/{deal}/personal-terms", headers=_headers(player), json={"wage_weekly": 90000, "length_years": 5})
    assert r.status_code == 403

    r = await client.put(f"/deals/{deal}/personal-terms", headers=_headers(ctx["buyer"]),
                         json={"wage_weekly": 50000, "length_years": 4})
    assert r.json()["proposed_by"] == "BUYER" and r.json()["agent_id"] is not None  # his agent may answer
    # The player counters himself; now it's the club's move.
    r = await client.put(f"/deals/{deal}/personal-terms", headers=_headers(player),
                         json={"wage_weekly": 70000, "length_years": 5, "note": "Five years, please"})
    assert r.status_code == 200 and r.json()["proposed_by"] == "PLAYER", r.text
    r = await client.post(f"/deals/{deal}/personal-terms/player-consent", headers=_headers(player), json={"agreement": "AGREED"})
    assert r.status_code == 400  # his own terms
    # The selling club can't answer them.
    r = await client.post(f"/deals/{deal}/personal-terms/club-respond", headers=_headers(ctx["seller"]), json={"agreement": "AGREED"})
    assert r.status_code == 400
    r = await client.post(f"/deals/{deal}/personal-terms/club-respond", headers=_headers(ctx["buyer"]), json={"agreement": "AGREED"})
    assert r.status_code == 200 and r.json()["player_consent"] == "AGREED", r.text
    assert Decimal(r.json()["wage_weekly"]) == 70000 and r.json()["length_years"] == 5

    # The player sees the terms' rounds but not the commission's.
    rounds = (await client.get(f"/deals/{deal}/term-proposals", headers=_headers(player))).json()
    assert [(x["kind"], x["side"]) for x in rounds] == [("PERSONAL_TERMS", "BUYER"), ("PERSONAL_TERMS", "PLAYER")]


async def test_the_club_walks_away_from_the_players_terms(client: AsyncClient, db: AsyncSession):
    ctx = await _setup_invited_deal(client, db)
    await _advance_to_personal_terms(client, ctx)
    await client.put(f"/deals/{ctx['deal_id']}/personal-terms", headers=_headers(ctx["invited_agent"]),
                     json={"wage_weekly": 400000, "length_years": 5})
    r = await client.post(f"/deals/{ctx['deal_id']}/personal-terms/club-respond", headers=_headers(ctx["buyer"]),
                          json={"agreement": "DECLINED", "reason": "Beyond our wage structure"})
    assert r.status_code == 200, r.text
    deal = (await client.get(f"/deals/{ctx['deal_id']}", headers=_headers(ctx["buyer"]))).json()
    assert deal["status"] == "COLLAPSED" and deal["collapse_reason"] == "Beyond our wage structure"


async def test_whose_move_follows_whose_terms_are_on_the_table(client: AsyncClient, db: AsyncSession):
    """The Board, the Dashboard and the deal list read whose_move (ADR 0012)."""
    ctx = await _setup_invited_deal(client, db)
    deal = ctx["deal_id"]
    buyer, seller, agent = _headers(ctx["buyer"]), _headers(ctx["seller"]), _headers(ctx["invited_agent"])

    async def moves():
        b = (await client.get(f"/deals/{deal}", headers=buyer)).json()["whose_move"]
        s = (await client.get(f"/deals/{deal}", headers=seller)).json()["whose_move"]
        return b, s

    async def on_dashboard():
        items = (await client.get("/clubs/me/dashboard", headers=buyer)).json()["waiting_on_you"]
        return next((i["reason"] for i in items if i["kind"] == "deal" and i["id"] == deal), None)

    assert await moves() == ("their", "neither")  # waiting on the agent's proposal
    await _propose(client, ctx)
    assert await moves() == ("your", "neither")
    assert await on_dashboard() == "Agent — commission to answer"
    await client.post(f"/deals/{deal}/agent-negotiation/club-counter", headers=buyer,
                      json={"commission_pct": 0.04, "commission_payer": "BUYER"})
    assert await moves() == ("their", "neither")  # the agent answers the counter
    assert await on_dashboard() is None
    await client.post(f"/deals/{deal}/agent-negotiation/agent-accept", headers=agent)
    assert await moves() == ("your", "neither")  # move it on
    await client.post(f"/deals/{deal}/advance", headers=buyer)

    assert await moves() == ("their", "neither")  # the agent opens with the terms
    await client.put(f"/deals/{deal}/personal-terms", headers=agent, json={"wage_weekly": 90000, "length_years": 5})
    assert await moves() == ("your", "neither")
    assert await on_dashboard() == "Personal terms — answer the player's side"
    await client.put(f"/deals/{deal}/personal-terms", headers=buyer, json={"wage_weekly": 70000, "length_years": 4})
    assert await moves() == ("their", "neither")  # the agent answers for him
    await client.post(f"/deals/{deal}/personal-terms/player-consent", headers=agent, json={"agreement": "AGREED"})
    assert await moves() == ("your", "your")  # either club moves it on

    board = (await client.get("/board", headers=buyer)).json()
    card = next(c for col in board["columns"] for c in col["cards"] if c["entity_id"] == deal)
    assert (card["whose_move"], card["detail"]) == ("your", "Personal terms · your move")
