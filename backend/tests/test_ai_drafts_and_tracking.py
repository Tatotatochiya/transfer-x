"""AI drafts, suggestion tracking and the filler filter.

No test calls a real model: `_llm_json` is the recording fake from
test_ai_assist. These check what the model is given (scoped facts, nothing
private), what TransferX does to its output (unknown figures dropped, hidden
clubs masked), and that suggestions are counted as shown and used.
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.ai.assist import keep_known_figures, useful_tips
from tests.conftest import _auth_headers, _register
from tests.test_ai_assist import buyer, fake_model, outsider, seller  # noqa: F401 (fixtures)
from tests.test_deals import _create_deal_via_offer, _create_player_for_seller


async def _events(db, feature: str) -> list[str]:
    from app.ai.models import AISuggestionEvent

    return [e.event for e in (await db.execute(
        select(AISuggestionEvent).where(AISuggestionEvent.feature == feature).order_by(AISuggestionEvent.created_at)
    )).scalars()]


# ── Pure helpers ──────────────────────────────────────────────────────────────


def test_unknown_figures_are_dropped_known_ones_kept():
    facts = {"agreed_fee": 5_000_000, "terms": {"wage_weekly": 35_000}}
    text = "We have agreed the £5m fee. We could stretch to £9m if needed. His wage stays at £35k a week."
    assert keep_known_figures(text, facts) == "We have agreed the £5m fee. His wage stays at £35k a week."


def test_filler_tips_and_restated_steps_are_dropped():
    steps = [{"label": "Buying club records a passed medical", "owner": "you"}]
    tips = [
        "Record the passed medical now — it's the only outstanding step and it's yours to complete.",
        "No deadline is set, but delay risks the move stalling; act today.",
        "His contract with Leeds runs to June 2027, so the £6m fee already reflects two years left.",
    ]
    assert useful_tips(tips, steps=steps) == [tips[2]]


# ── Drafts ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_deal_draft_keeps_only_known_figures_and_is_counted(client: AsyncClient, buyer, seller, db, fake_model):  # noqa: F811
    calls, reply = fake_model
    deal = await _create_deal_via_offer(client, buyer, seller, db, fee=5_000_000)
    reply["DRAFT_MESSAGE_USER"] = {"text": "We are pleased the £5m fee is agreed. We would also pay £9m in add-ons."}

    resp = await client.post("/ai/draft", json={"kind": "deal_message", "id": deal["id"], "intent": "thank them"},
                             headers=_auth_headers(buyer))
    assert resp.status_code == 200, resp.text
    assert resp.json()["text"] == "We are pleased the £5m fee is agreed."
    facts = calls[-1]["facts"]
    assert facts["agreed_fee"] == 5_000_000 and "budget" not in str(facts).lower()
    assert calls[-1]["fmt"]["intent"] == "thank them"
    assert await _events(db, "draft_deal_message") == ["SHOWN"]

    # The page reports it sent; only drafts may be reported this way.
    ok = await client.post("/ai/suggestions/used", json={"feature": "draft_deal_message", "ref": deal["id"]},
                           headers=_auth_headers(buyer))
    assert ok.status_code == 204
    assert await _events(db, "draft_deal_message") == ["SHOWN", "USED"]
    bad = await client.post("/ai/suggestions/used", json={"feature": "counter_advisor"}, headers=_auth_headers(buyer))
    assert bad.status_code == 422


@pytest.mark.asyncio
async def test_drafts_are_for_parties_only(client: AsyncClient, buyer, seller, outsider, db, fake_model):  # noqa: F811
    deal = await _create_deal_via_offer(client, buyer, seller, db)
    resp = await client.post("/ai/draft", json={"kind": "deal_message", "id": deal["id"]}, headers=_auth_headers(outsider))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_offer_note_never_sees_the_budget(client: AsyncClient, buyer, seller, db, fake_model):  # noqa: F811
    from tests.test_ai_assist import _offer

    calls, reply = fake_model
    offer = await _offer(client, buyer, seller, db)
    reply["DRAFT_MESSAGE_USER"] = {"text": "Our offer stands at £5m for the player."}
    resp = await client.post("/ai/draft", json={"kind": "counter_note", "id": offer["id"]}, headers=_auth_headers(buyer))
    assert resp.status_code == 200, resp.text
    facts = calls[-1]["facts"]
    assert "your_budget" not in facts and "competing_offers" not in facts
    assert facts["current_terms"]["fee_amount"] == 5_000_000
    assert facts["you_are"].startswith("the BUYING club") and facts["the_player_is_under_contract_with"] != "you"


@pytest.mark.asyncio
async def test_offer_note_for_the_selling_club_says_it_is_selling(client: AsyncClient, buyer, seller, db, fake_model):  # noqa: F811
    """A selling club's draft once read "we would like to sign him": the facts
    now say plainly which side the club is on and who wrote the terms."""
    from tests.test_ai_assist import _offer

    calls, reply = fake_model
    offer = await _offer(client, buyer, seller, db)
    reply["DRAFT_MESSAGE_USER"] = {"text": "Thank you for your offer of £5m."}
    resp = await client.post("/ai/draft", json={"kind": "counter_note", "id": offer["id"]}, headers=_auth_headers(seller))
    assert resp.status_code == 200, resp.text
    facts, fmt = calls[-1]["facts"], calls[-1]["fmt"]
    assert facts["you_are"].startswith("the SELLING club")
    assert facts["the_player_is_under_contract_with"] == "you"
    assert facts["current_terms_were_sent_by"] == "them"
    assert "buying club" in facts["you_are_writing_to"]
    assert "reply, as the selling club" in fmt["purpose"]


@pytest.mark.asyncio
async def test_enquiry_reply_masks_an_anonymous_asking_club(client: AsyncClient, buyer, seller, db, fake_model):  # noqa: F811
    calls, reply = fake_model
    player = await _create_player_for_seller(client, _auth_headers(seller))
    resp = await client.post("/enquiries", json={"player_id": player["id"], "body": "Is he available?", "is_anonymous": True},
                             headers=_auth_headers(buyer))
    assert resp.status_code == 201, resp.text
    enquiry_id = resp.json()["id"]
    # The model slips and names the hidden club; TransferX masks it.
    reply["DRAFT_MESSAGE_USER"] = {"text": "Thank you, Hidden Buyer FC. He is not for sale this window."}
    resp = await client.post("/ai/draft", json={"kind": "enquiry_reply", "id": enquiry_id}, headers=_auth_headers(seller))
    assert resp.status_code == 200, resp.text
    assert "Hidden Buyer" not in resp.json()["text"] and "undisclosed" in resp.json()["text"]
    assert "Hidden Buyer" not in str(calls[-1]["facts"])


# ── Suggestion tracking ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_counter_advice_is_counted_shown_then_used(client: AsyncClient, buyer, seller, db, fake_model):  # noqa: F811
    from app.auth.models import User
    from tests.test_ai_assist import _offer

    calls, reply = fake_model
    offer = await _offer(client, buyer, seller, db)
    reply["OFFER_ADVICE_USER"] = {"summary": "Close to value.", "recommendation": "counter",
                                  "suggested_terms": {"fee_amount": 6_000_000}, "reasons": ["Model says more."]}
    resp = await client.get(f"/ai/offers/{offer['id']}/advice", headers=_auth_headers(seller))
    assert resp.status_code == 200, resp.text
    resp = await client.post(f"/offers/{offer['id']}/counter", json={"fee_amount": 6_000_000, "ai_assisted": True},
                             headers=_auth_headers(seller))
    assert resp.status_code == 200, resp.text
    assert await _events(db, "counter_advisor") == ["SHOWN", "USED"]

    admin_email = f"admin-{uuid.uuid4()}@test.com"
    admin = await _register(client, admin_email)
    (await db.execute(select(User).where(User.email == admin_email))).scalar_one().is_superuser = True
    await db.commit()
    stats = await client.get("/ai/suggestions/stats", headers=_auth_headers(admin))
    assert stats.status_code == 200, stats.text
    row = next(f for f in stats.json()["features"] if f["feature"] == "counter_advisor")
    assert (row["shown"], row["used"], row["used_pct"]) == (1, 1, 100)
    assert (await client.get("/ai/suggestions/stats", headers=_auth_headers(buyer))).status_code == 403


def test_verdict_rule_for_trimming_the_assistant():
    from app.ai.tracking import verdict

    assert verdict(10, 90) == "Not enough data yet"
    assert verdict(40, 30) == "Keep"
    assert verdict(40, 15) == "Review"
    assert verdict(40, 5) == "Consider removing"
    assert verdict(0, None) == "Not enough data yet"
