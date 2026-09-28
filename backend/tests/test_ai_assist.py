"""The workflow assistant (app/ai/assist.py, architecture ADR 0006).

No test calls a real model: `_llm_json` is replaced by a fake that records
the facts it was given, so these tests check what matters most — what each
club's facts contain, that TransferX (not the model) computes the numbers,
and that model output is validated before it reaches the page.
"""

import json
from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import AsyncClient

from app.config import settings
from tests.conftest import _auth_headers, _register
from tests.test_deals import _create_deal_via_offer, _create_player_for_seller, _get_club_id, _give_budget


@pytest_asyncio.fixture
async def buyer(client: AsyncClient) -> dict:
    return await _register(client, "buyer_ai@test.com", club_name="Hidden Buyer FC")


@pytest_asyncio.fixture
async def seller(client: AsyncClient) -> dict:
    return await _register(client, "seller_ai@test.com", club_name="Selling Side FC")


@pytest_asyncio.fixture
async def outsider(client: AsyncClient) -> dict:
    return await _register(client, "outsider_ai@test.com", club_name="Nosy Neighbours FC")


@pytest.fixture
def no_model(monkeypatch):
    for key in ("anthropic_api_key", "openai_api_key", "deepseek_api_key"):
        monkeypatch.setattr(settings, key, None)


@pytest.fixture
def fake_model(monkeypatch):
    """A model that answers `reply[prompt_key]` and records every call."""
    from app.ai import assist

    monkeypatch.setattr(settings, "anthropic_api_key", "test-key")
    calls: list[dict] = []
    reply: dict = {}

    async def fake(prompt_key, *, user_id, endpoint, max_tokens=900, **fmt):
        calls.append({"prompt_key": prompt_key, "facts": json.loads(fmt.get("facts_json", "{}")), "fmt": fmt})
        return reply.get(prompt_key, {})

    monkeypatch.setattr(assist, "_llm_json", fake)
    return calls, reply


async def _offer(client, buyer, seller, db, *, fee=5_000_000, anonymous=False) -> dict:
    await _give_budget(db)
    player = await _create_player_for_seller(client, _auth_headers(seller))
    seller_club_id = await _get_club_id(client, _auth_headers(seller))
    resp = await client.post(
        "/offers",
        json={"player_id": player["id"], "to_club_id": seller_club_id, "fee_amount": fee,
              "wage_weekly": 20000, "contract_years": 3, "is_anonymous": anonymous},
        headers=_auth_headers(buyer),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# ── Rule-based checks: no model involved ─────────────────────────────────────


@pytest.mark.asyncio
async def test_offer_check_flags_budget_contract_and_sell_on(client, buyer, seller, db, no_model):
    await _give_budget(db, Decimal("10000000"))
    player = await _create_player_for_seller(client, _auth_headers(seller))
    resp = await client.post(
        "/ai/offer-check",
        json={"terms": {"player_id": player["id"], "deal_type": "PERMANENT", "fee_amount": 50_000_000,
                        "contract_years": 7, "sell_on_pct": 0.4}},
        headers=_auth_headers(buyer),
    )
    assert resp.status_code == 200, resp.text
    codes = {w["code"] for w in resp.json()["warnings"]}
    assert {"over_transfer_budget", "contract_too_long", "high_sell_on"} <= codes
    assert resp.json()["warnings"][0]["severity"] == "high"


@pytest.mark.asyncio
async def test_offer_check_on_someone_elses_offer_is_refused(client, buyer, seller, outsider, db, no_model):
    offer = await _offer(client, buyer, seller, db)
    resp = await client.post(
        "/ai/offer-check", json={"offer_id": offer["id"], "terms": {}}, headers=_auth_headers(outsider)
    )
    assert resp.status_code == 404


# ── Deal next steps: computed from the stage machine ─────────────────────────


@pytest.mark.asyncio
async def test_deal_next_steps_work_without_a_model(client, buyer, seller, outsider, db, no_model):
    deal = await _create_deal_via_offer(client, buyer, seller, db)
    resp = await client.get(f"/ai/deals/{deal['id']}/next-steps", headers=_auth_headers(buyer))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["steps"] == [{"label": "Move the deal on to personal terms", "owner": "either"}]
    assert body["brief"] is None

    await client.post(f"/deals/{deal['id']}/advance", headers=_auth_headers(buyer))
    steps = (await client.get(f"/ai/deals/{deal['id']}/next-steps", headers=_auth_headers(seller))).json()["steps"]
    # The seller sees the buyer's step as the other side's.
    assert steps == [{"label": "Propose personal terms to the player", "owner": "them"}]

    # Terms proposed to a player with no account or agent: the buying club
    # records his answer (ADR 0006), so the step is the buyer's.
    await client.put(f"/deals/{deal['id']}/personal-terms", json={"wage_weekly": 40000}, headers=_auth_headers(buyer))
    steps = (await client.get(f"/ai/deals/{deal['id']}/next-steps", headers=_auth_headers(buyer))).json()["steps"]
    assert steps == [{"label": "Record the player's answer, with the signed terms", "owner": "you"}]

    assert (await client.get(f"/ai/deals/{deal['id']}/next-steps", headers=_auth_headers(outsider))).status_code == 404


# ── What each side's facts contain ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_advice_facts_are_scoped_to_the_viewer(client, buyer, seller, db, fake_model):
    calls, reply = fake_model
    reply["OFFER_ADVICE_USER"] = {"recommendation": "accept", "summary": "ok"}
    offer = await _offer(client, buyer, seller, db, anonymous=True)

    resp = await client.get(f"/ai/offers/{offer['id']}/advice", headers=_auth_headers(seller))
    assert resp.status_code == 200, resp.text
    seller_facts = calls[-1]["facts"]
    # The seller's model never learns who the anonymous buyer is, nor its budget.
    assert "Hidden Buyer FC" not in json.dumps(calls[-1]["fmt"])
    assert seller_facts["other_club"] == "an undisclosed club"
    assert "your_budget" not in seller_facts
    assert "competing_offers" in seller_facts

    resp = await client.get(f"/ai/offers/{offer['id']}/advice", headers=_auth_headers(buyer))
    assert resp.status_code == 200, resp.text
    buyer_facts = calls[-1]["facts"]
    # The buyer sees its own budget, never the seller's order book.
    assert "your_budget" in buyer_facts
    assert "competing_offers" not in buyer_facts
    # Not the buyer's turn: whatever the model says, the advice is to wait.
    assert resp.json()["recommendation"] == "wait"


@pytest.mark.asyncio
async def test_suggested_counter_is_validated(client, buyer, seller, db, fake_model):
    calls, reply = fake_model
    reply["OFFER_ADVICE_USER"] = {
        "recommendation": "counter",
        "summary": "Push for more.",
        "suggested_terms": {
            "fee_amount": 500_000_000,   # 100× the offer: dropped
            "sell_on_pct": 15,           # a percentage: read as 0.15
            "contract_years": 9,         # over five years: dropped
            "wage_weekly": 25000,
            "made_up_term": 1,           # not a term: dropped
        },
    }
    offer = await _offer(client, buyer, seller, db)
    advice = (await client.get(f"/ai/offers/{offer['id']}/advice", headers=_auth_headers(seller))).json()
    assert advice["recommendation"] == "counter"
    assert advice["suggested_terms"] == {"sell_on_pct": 0.15, "wage_weekly": 25000.0}

    # Cached until the offer moves: asking again makes no second model call.
    before = len(calls)
    again = (await client.get(f"/ai/offers/{offer['id']}/advice", headers=_auth_headers(seller))).json()
    assert again["cached"] is True and len(calls) == before


@pytest.mark.asyncio
async def test_advice_is_for_the_parties_only(client, buyer, seller, outsider, db, fake_model):
    offer = await _offer(client, buyer, seller, db)
    resp = await client.get(f"/ai/offers/{offer['id']}/advice", headers=_auth_headers(outsider))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_negotiation_moves_are_attributed_by_transferx(client, buyer, seller, db, fake_model):
    calls, _ = fake_model
    offer = await _offer(client, buyer, seller, db)
    r = await client.post(f"/offers/{offer['id']}/counter", json={"fee_amount": 7_000_000}, headers=_auth_headers(seller))
    assert r.status_code == 200, r.text
    r = await client.post(f"/offers/{offer['id']}/counter", json={"fee_amount": 6_000_000}, headers=_auth_headers(buyer))
    assert r.status_code == 200, r.text

    resp = await client.get(f"/ai/offers/{offer['id']}/summary", headers=_auth_headers(seller))
    assert resp.status_code == 200, resp.text
    facts = calls[-1]["facts"]
    assert facts["moves_by_you"] == ["fee up from 5,000,000 to 7,000,000"]
    assert facts["moves_by_them"] == ["fee down from 7,000,000 to 6,000,000"]
    assert resp.json()["rounds"] == 2


@pytest.mark.asyncio
async def test_ask_keeps_only_links_from_the_facts(client, buyer, seller, db, fake_model):
    calls, reply = fake_model
    reply["ASK_USER"] = {
        "answer": "You have one transfer in progress.",
        "links": [{"label": "Somewhere else", "path": "https://evil.example"},
                  {"label": "Transfers", "path": "/deals"}],
    }
    await _create_deal_via_offer(client, buyer, seller, db)
    resp = await client.post("/ai/ask", json={"question": "What is in progress?"}, headers=_auth_headers(buyer))
    assert resp.status_code == 200, resp.text
    assert resp.json()["links"] == [{"label": "Transfers", "path": "/deals"}]
    # Only the asking club's own data went to the model.
    assert "your_listings" in calls[-1]["facts"] and calls[-1]["facts"]["club"] == "Hidden Buyer FC"


@pytest.mark.asyncio
async def test_seller_tools_are_for_the_owning_club(client, buyer, seller, db, no_model):
    player = await _create_player_for_seller(client, _auth_headers(seller))
    mine = await client.get(f"/ai/listing-advice/{player['id']}", headers=_auth_headers(seller))
    assert mine.status_code == 200, mine.text
    assert mine.json()["availability"] in ("TRANSFER", "LOAN", "EITHER")
    for path in (f"/ai/listing-advice/{player['id']}", f"/ai/potential-buyers/{player['id']}"):
        assert (await client.get(path, headers=_auth_headers(buyer))).status_code == 404


@pytest.mark.asyncio
async def test_model_features_answer_503_without_a_model(client, buyer, seller, db, no_model):
    offer = await _offer(client, buyer, seller, db)
    resp = await client.get(f"/ai/offers/{offer['id']}/advice", headers=_auth_headers(seller))
    assert resp.status_code == 503
    status = (await client.get("/ai/status", headers=_auth_headers(seller))).json()
    assert status["available"] is False
