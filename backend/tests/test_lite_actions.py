"""Lite action cards and the money panel (docs/feature_spec/lite-mode, L4).

The money block on /ai/offer-check must agree with the refusal the offer
endpoints make, and with the spending-approval rule; the action card
endpoints only describe, never act.
"""

import uuid
from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select

from app.ai.assist import money_effect
from app.config import settings
from tests.conftest import _auth_headers, _register
from tests.test_capabilities import _create_staff
from tests.test_deals import _create_player_for_seller, _get_club_id, _give_budget


@pytest.fixture(autouse=True)
def no_model(monkeypatch):
    for key in ("anthropic_api_key", "openai_api_key", "deepseek_api_key"):
        monkeypatch.setattr(settings, key, None)


@pytest_asyncio.fixture
async def buyer(client: AsyncClient) -> dict:
    return await _register(client, "buyer_act@test.com", club_name="Card Buyers FC")


@pytest_asyncio.fixture
async def seller(client: AsyncClient) -> dict:
    return await _register(client, "seller_act@test.com", club_name="Card Sellers FC")


async def _budget(db, transfer: int, wage: int = 1_000_000):
    from app.clubs.models import ClubFinance

    for f in (await db.execute(select(ClubFinance))).scalars():
        f.transfer_budget_total = Decimal(transfer)
        f.wage_budget_total_weekly = Decimal(wage)
    await db.commit()


async def _check(client, club, body) -> dict:
    resp = await client.post("/ai/offer-check", json=body, headers=_auth_headers(club))
    assert resp.status_code == 200, resp.text
    return resp.json()


def _over_warned(check: dict) -> bool:
    return any(w["code"] in ("over_transfer_budget", "over_wage_budget") for w in check["warnings"])


async def _send(client, buyer, seller, player_id, fee, *, anonymous=False) -> dict:
    resp = await client.post("/offers", json={
        "player_id": player_id, "to_club_id": await _get_club_id(client, _auth_headers(seller)),
        "fee_amount": fee, "wage_weekly": 20_000, "contract_years": 3, "is_anonymous": anonymous,
    }, headers=_auth_headers(buyer))
    assert resp.status_code == 201, resp.text
    return resp.json()


# ── The money block agrees with the refusal ─────────────────────────────────


@pytest.mark.asyncio
async def test_money_agrees_with_warnings_and_refusal(client: AsyncClient, buyer, seller, db):
    """BACKEND.md §4's table: a bid inside and over budget, an add-on that
    tips it over, a counter raising the fee, and the seller accepting."""
    await _budget(db, 10_000_000, wage=100_000)
    player = await _create_player_for_seller(client, _auth_headers(seller))
    to_club = await _get_club_id(client, _auth_headers(seller))
    base = {"player_id": player["id"], "to_club_id": to_club, "wage_weekly": 20_000, "contract_years": 3}

    inside = await _check(client, buyer, {"terms": {**base, "fee_amount": 8_000_000}})
    m = inside["money"]
    assert (m["transfer_before"], m["this_action"], m["transfer_after"]) == (10_000_000, 8_000_000, 2_000_000)
    assert (m["wage_before_weekly"], m["wage_after_weekly"]) == (100_000, 80_000)
    assert m["transfer_budget"] == 10_000_000
    assert m["over_budget"] is False and not _over_warned(inside)

    # An add-on is reserved with the fee, so it counts against the budget —
    # the old warning looked at the fee alone and missed this.
    clause = {"clause_type": "APPEARANCES", "trigger_description": "50 games", "amount": "3000000"}
    tipped = await _check(client, buyer, {"terms": {**base, "fee_amount": 8_000_000, "clauses": [clause]}})
    assert tipped["money"]["over_budget"] is True and _over_warned(tipped)
    refused = await client.post("/offers", json={**base, "fee_amount": 8_000_000, "clauses": [clause]},
                                headers=_auth_headers(buyer))
    assert refused.status_code == 400 and "Insufficient transfer budget" in refused.text

    over_wage = await _check(client, buyer, {"terms": {**base, "fee_amount": 1_000_000, "wage_weekly": 150_000}})
    assert over_wage["money"]["over_budget"] is True
    assert {w["code"] for w in over_wage["warnings"]} >= {"over_wage_budget"}

    # A counter only needs the difference: £8m held, £9m asked needs £1m more
    # of the £2m left.
    offer = await _send(client, buyer, seller, player["id"], 8_000_000)
    raise_ok = await _check(client, buyer, {"offer_id": offer["id"], "terms": {"fee_amount": 9_000_000}})
    assert raise_ok["money"]["this_action"] == 1_000_000
    assert raise_ok["money"]["transfer_before"] == 2_000_000
    assert raise_ok["money"]["over_budget"] is False and not _over_warned(raise_ok)
    raise_over = await _check(client, buyer, {"offer_id": offer["id"], "terms": {"fee_amount": 10_500_000}})
    assert raise_over["money"]["over_budget"] is True and _over_warned(raise_over)

    # The seller's side: the fee comes in when the deal completes; no wage line.
    selling = await _check(client, seller, {"offer_id": offer["id"], "terms": {}})
    sm = selling["money"]
    assert sm["on_completion"] is True and sm["over_budget"] is False
    assert sm["this_action"] == 8_000_000
    assert sm["transfer_after"] == sm["transfer_before"] + 8_000_000
    assert sm["wage_after_weekly"] is None


def test_loan_money_uses_the_wage_split():
    budget = {"transfer_budget_remaining": 1_000_000.0, "wage_budget_remaining_weekly": 30_000.0,
              "transfer_budget_total": 1_000_000.0}
    terms = {"deal_type": "LOAN", "loan_fee": 500_000, "wage_weekly": 50_000, "wage_split_pct": 0.5}
    m = money_effect(terms, role="buyer", budget=budget)
    assert (m["this_action"], m["wage_this_action"], m["wage_after_weekly"]) == (500_000, 25_000, 5_000)
    assert m["over_budget"] is False
    m = money_effect({**terms, "wage_split_pct": 0.7}, role="buyer", budget=budget)
    assert m["over_wage"] is True and m["over_budget"] is True


@pytest.mark.asyncio
async def test_requires_approval_follows_the_club_rule(client: AsyncClient, buyer, seller, db):
    await _give_budget(db)
    player = await _create_player_for_seller(client, _auth_headers(seller))
    manager = await _create_staff(client, db, _auth_headers(buyer), "act_mgr@test.com", "MANAGER")
    resp = await client.patch("/clubs/me/approval-policy", json={"approval_threshold": 5_000_000},
                              headers=_auth_headers(buyer))
    assert resp.status_code == 200, resp.text
    terms = {"player_id": player["id"], "wage_weekly": 20_000}

    assert (await _check(client, manager, {"terms": {**terms, "fee_amount": 6_000_000}}))["money"]["requires_approval"] is True
    assert (await _check(client, manager, {"terms": {**terms, "fee_amount": 4_000_000}}))["money"]["requires_approval"] is False
    # Owners are never escalated.
    assert (await _check(client, buyer, {"terms": {**terms, "fee_amount": 6_000_000}}))["money"]["requires_approval"] is False

    # ...and the real endpoint agrees: the manager's £6m offer is captured.
    sent = await client.post("/offers", json={**terms, "fee_amount": 6_000_000,
                                              "to_club_id": await _get_club_id(client, _auth_headers(seller))},
                             headers=_auth_headers(manager))
    assert sent.status_code == 202 and sent.json()["status"] == "PENDING_APPROVAL"


# ── ai_assisted on create, accept and reject ────────────────────────────────


async def _ai_events(db, entity_id: str) -> list:
    from app.audit.models import AuditEvent

    return (await db.execute(select(AuditEvent).where(
        AuditEvent.entity_id == uuid.UUID(entity_id), AuditEvent.action == "AI_SUGGESTION_USED"))).scalars().all()


@pytest.mark.asyncio
async def test_ai_assisted_is_audited_on_create_accept_and_reject(client: AsyncClient, buyer, seller, db):
    await _give_budget(db)
    p1 = await _create_player_for_seller(client, _auth_headers(seller))
    to_club = await _get_club_id(client, _auth_headers(seller))
    resp = await client.post("/offers", json={"player_id": p1["id"], "to_club_id": to_club, "fee_amount": 5_000_000,
                                              "ai_assisted": True}, headers=_auth_headers(buyer))
    assert resp.status_code == 201, resp.text
    first = resp.json()
    assert len(await _ai_events(db, first["id"])) == 1

    resp = await client.post(f"/offers/{first['id']}/reject", json={"ai_assisted": True}, headers=_auth_headers(seller))
    assert resp.status_code == 200, resp.text
    assert len(await _ai_events(db, first["id"])) == 2

    p2 = await _create_player_for_seller(client, _auth_headers(seller))
    second = await _send(client, buyer, seller, p2["id"], 5_000_000)
    assert await _ai_events(db, second["id"]) == []
    resp = await client.post(f"/offers/{second['id']}/accept", json={"ai_assisted": True}, headers=_auth_headers(seller))
    assert resp.status_code == 200, resp.text
    assert len(await _ai_events(db, second["id"])) == 1

    # No body at all still works, as the full app sends it.
    p3 = await _create_player_for_seller(client, _auth_headers(seller))
    third = await _send(client, buyer, seller, p3["id"], 5_000_000)
    assert (await client.post(f"/offers/{third['id']}/reject", headers=_auth_headers(seller))).status_code == 200
    assert await _ai_events(db, third["id"]) == []


# ── The action card endpoints ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_offer_draft_starts_from_the_price_and_says_why_not(client: AsyncClient, buyer, seller, db):
    from tests.test_lite_buy import _value

    await _give_budget(db)
    player = await _create_player_for_seller(client, _auth_headers(seller))
    await _value(db, player["id"], 7_300_000)

    resp = await client.get(f"/lite/offer-draft?player_id={player['id']}", headers=_auth_headers(buyer))
    assert resp.status_code == 200, resp.text
    d = resp.json()
    assert d["fee"] == 7_500_000 and d["fee_basis"] == "model"  # to the nearest £0.5m
    assert d["to_club_name"] == "Card Sellers FC"
    assert d["to_club_id"] == await _get_club_id(client, _auth_headers(seller))
    assert d["disabled_reason"] is None

    # His own club can't bid for him.
    own = await client.get(f"/lite/offer-draft?player_id={player['id']}", headers=_auth_headers(seller))
    assert own.status_code == 409

    # A role that can't send offers sees the card disabled, with the reason.
    readonly = await _create_staff(client, db, _auth_headers(buyer), "act_ro@test.com", "READONLY")
    ro = (await client.get(f"/lite/offer-draft?player_id={player['id']}", headers=_auth_headers(readonly))).json()
    assert "Your role can't" in ro["disabled_reason"]

    # With an offer already in, the card says so and points at it.
    offer = await _send(client, buyer, seller, player["id"], 7_000_000)
    again = (await client.get(f"/lite/offer-draft?player_id={player['id']}", headers=_auth_headers(buyer))).json()
    assert again["existing_offer_id"] == offer["id"] and again["disabled_reason"]


@pytest.mark.asyncio
async def test_offer_card_masks_anonymous_buyers_and_suggests_a_counter(client: AsyncClient, buyer, seller, db):
    await _give_budget(db)
    player = await _create_player_for_seller(client, _auth_headers(seller))
    offer = await _send(client, buyer, seller, player["id"], 6_000_000, anonymous=True)

    card = (await client.get(f"/lite/offers/{offer['id']}", headers=_auth_headers(seller))).json()
    assert card["side"] == "seller" and card["your_move"] is True
    assert "undisclosed" in card["other_club"] and "Card Buyers" not in str(card)
    assert card["counter_suggestion"] >= 6_600_000 and card["counter_suggestion"] % 500_000 == 0
    assert card["disabled_reason"] is None

    mine = (await client.get(f"/lite/offers/{offer['id']}", headers=_auth_headers(buyer))).json()
    assert mine["side"] == "buyer" and mine["your_move"] is False
    assert mine["other_club"] == "Card Sellers FC"
    assert mine["disabled_reason"].startswith("Waiting for")

    outsider = await _register(client, "outsider_act@test.com", club_name="Nosy FC")
    assert (await client.get(f"/lite/offers/{offer['id']}", headers=_auth_headers(outsider))).status_code == 404
