"""Ask anything in Lite (docs/feature_spec/lite-mode, L5, BACKEND.md §3).

The model is the recording fake from test_ai_assist. These check that a
proposal is only returned once TransferX has checked it (kind, player or
offer, amount, role), that Lite links are allowed, and that every question
is logged.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from tests.conftest import _auth_headers, _register
from tests.test_ai_assist import _offer, buyer, fake_model, seller  # noqa: F401 (fixtures)
from tests.test_capabilities import _create_staff
from tests.test_deals import _give_budget
from tests.test_lite_buy import _player, _value


async def _ask(client, club, question="bid for him", **extra):
    resp = await client.post("/ai/ask", json={"question": question, "lite": True, **extra}, headers=_auth_headers(club))
    assert resp.status_code == 200, resp.text
    return resp.json()


async def _questions(db):
    from app.ai.models import AssistantQuery

    return (await db.execute(select(AssistantQuery).order_by(AssistantQuery.created_at))).scalars().all()


@pytest.mark.asyncio
async def test_a_bid_proposal_is_checked_and_opens_the_card(client: AsyncClient, buyer, seller, db, fake_model):  # noqa: F811
    calls, reply = fake_model
    await _give_budget(db)
    target = await _player(client, seller, "Ellis Varga")
    await _value(db, target["id"], 8_000_000)

    reply["ASK_LITE_USER"] = {"answer": "I've prepared a bid.", "links": [{"label": "Buy", "path": "/lite/buy"}],
                              "proposal": {"kind": "bid", "player": "Ellis Varga", "amount": 8_000_000}}
    got = await _ask(client, buyer, "bid £8m for Ellis Varga", input="voice")
    p = got["proposal"]
    assert (p["kind"], p["player"], p["amount"], p["club"]) == ("bid", "Ellis Varga", 8_000_000, "Selling Side FC")
    assert p["card_path"] == f"/lite/bid?player_id={target['id']}&fee=8000000&from=ask"
    assert p["prefill"]["fee_amount"] == 8_000_000 and p["prefill"]["to_club_id"]
    assert got["links"] == [{"label": "Buy", "path": "/lite/buy"}]  # a Lite page is an allowed link
    assert "lite_player_searches" in calls[-1]["facts"]
    # The answer comes from the check, not the model, so it never contradicts it.
    assert got["answer"] == "I've prepared a £8m bid for Ellis Varga (Selling Side FC) for you to check."

    # Far above anything known about him: no proposal, just his page.
    reply["ASK_LITE_USER"]["proposal"] = {"kind": "bid", "player": "Ellis Varga", "amount": 40_000_000}
    got = await _ask(client, buyer, "bid £40m for Ellis Varga")
    assert got["proposal"] is None
    assert {"label": "Ellis Varga", "path": f"/players/market/{target['id']}"} in got["links"]
    assert got["answer"].startswith("£40m is too far from his price of about £8m")

    logged = await _questions(db)
    assert [(q.input, q.lite, q.had_proposal) for q in logged] == [("voice", True, True), ("text", True, False)]


@pytest.mark.asyncio
async def test_an_ambiguous_name_gives_candidates_not_a_proposal(client: AsyncClient, buyer, seller, db, fake_model):  # noqa: F811
    calls, reply = fake_model
    for name in ("Sam Okafor", "Sam Oduya"):
        created = await _player(client, seller, name)
        await _value(db, created["id"], 5_000_000)
    reply["ASK_LITE_USER"] = {"answer": "Which Sam?", "links": [],
                              "proposal": {"kind": "bid", "player": "Sam O", "amount": 5_000_000}}
    got = await _ask(client, buyer)
    assert got["proposal"] is None
    assert sorted(lnk["label"] for lnk in got["links"]) == ["Sam Oduya", "Sam Okafor"]


@pytest.mark.asyncio
async def test_a_role_that_cannot_send_offers_gets_no_proposal(client: AsyncClient, buyer, seller, db, fake_model):  # noqa: F811
    calls, reply = fake_model
    target = await _player(client, seller, "Ellis Varga")
    await _value(db, target["id"], 8_000_000)
    readonly = await _create_staff(client, db, _auth_headers(buyer), "ask_ro@test.com", "READONLY")
    reply["ASK_LITE_USER"] = {"answer": "Here.", "links": [],
                              "proposal": {"kind": "bid", "player": "Ellis Varga", "amount": 8_000_000}}
    assert (await _ask(client, readonly))["proposal"] is None


@pytest.mark.asyncio
async def test_counter_and_accept_proposals_need_the_clubs_move(client: AsyncClient, buyer, seller, db, fake_model):  # noqa: F811
    calls, reply = fake_model
    offer = await _offer(client, buyer, seller, db, fee=5_000_000)
    path = f"/offers/{offer['id']}"

    reply["ASK_LITE_USER"] = {"answer": "Ready.", "links": [],
                              "proposal": {"kind": "counter", "offer_path": path, "amount": 6_000_000}}
    got = await _ask(client, seller, "counter at £6m")
    assert got["proposal"]["card_path"] == f"/lite/offers/{offer['id']}?action=counter&from=ask&amount=6000000"

    reply["ASK_LITE_USER"]["proposal"] = {"kind": "accept", "offer_path": path}
    got = await _ask(client, seller, "accept it")
    assert got["proposal"]["card_path"] == f"/lite/offers/{offer['id']}?action=accept&from=ask"

    # The buyer is waiting on the seller: it is not the buyer's move.
    reply["ASK_LITE_USER"]["proposal"] = {"kind": "accept", "offer_path": path}
    assert (await _ask(client, buyer, "accept it"))["proposal"] is None


@pytest.mark.asyncio
async def test_full_app_ask_never_proposes_and_a_failure_in_lite_falls_back(client: AsyncClient, buyer, seller, db, fake_model, monkeypatch):  # noqa: F811
    calls, reply = fake_model
    reply["ASK_USER"] = {"answer": "You have plenty.", "links": [], "proposal": {"kind": "bid", "player": "X"}}
    resp = await client.post("/ai/ask", json={"question": "how much can we spend?"}, headers=_auth_headers(buyer))
    assert resp.status_code == 200 and resp.json()["proposal"] is None
    assert calls[-1]["prompt_key"] == "ASK_USER"

    from app.ai import assist

    async def broken(*a, **k):
        raise RuntimeError("model down")

    monkeypatch.setattr(assist, "_llm_json", broken)
    got = await _ask(client, buyer, "anything new?")
    assert got["fallback"] is True and got["answer"] is None and got["links"]
    assert (await _questions(db))[-1].fallback is True


@pytest.mark.asyncio
async def test_suggestions_come_from_the_clubs_state(client: AsyncClient, buyer, seller, db):  # noqa: F811
    await _give_budget(db)
    await _offer(client, buyer, seller, db)
    resp = await client.get("/lite/ask/suggestions", headers=_auth_headers(seller))
    assert resp.status_code == 200, resp.text
    suggestions = resp.json()["suggestions"]
    assert len(suggestions) == 4 and suggestions[0] == "What's happening with Deal Player?"
    assert any(s.startswith("Find me a ") for s in suggestions)
    other = await _register(client, "ask_none@test.com", club_name="Quiet FC")
    assert len((await client.get("/lite/ask/suggestions", headers=_auth_headers(other))).json()["suggestions"]) == 3


@pytest.mark.asyncio
async def test_a_plain_bid_request_is_prepared_even_if_the_model_gives_no_proposal(client: AsyncClient, buyer, seller, db, fake_model):  # noqa: F811
    calls, reply = fake_model
    target = await _player(client, seller, "Ellis Varga")
    await _value(db, target["id"], 8_000_000)
    reply["ASK_LITE_USER"] = {"answer": "I can't find him in your data.", "links": [], "proposal": None}
    got = await _ask(client, buyer, "put in a £7.5m bid for Ellis Varga")
    assert got["proposal"]["amount"] == 7_500_000
    assert got["answer"] == "I've prepared a £7.5m bid for Ellis Varga (Selling Side FC) for you to check."
