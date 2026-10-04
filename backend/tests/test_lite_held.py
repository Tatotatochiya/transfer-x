"""Lite L6: held sends for undo, and plain progress (architecture ADR 0007).

The contract: a confirmed action is checked at once, held for 10 seconds
with nothing sent, notified or reserved, can be undone without trace, and is
then sent by the normal endpoint as the person who confirmed it."""
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import func, select

from app.clubs.models import ClubFinance
from app.config import settings
from app.lite import held
from app.lite.models import HeldAction, HeldActionStatus
from app.notifications.models import Notification
from app.offers.models import Offer
from tests.conftest import _auth_headers, _register
from tests.test_deals import _create_player_for_seller, _get_club_id

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def no_model(monkeypatch):
    for key in ("anthropic_api_key", "openai_api_key", "deepseek_api_key"):
        monkeypatch.setattr(settings, key, None)


@pytest_asyncio.fixture
async def buyer(client: AsyncClient) -> dict:
    return await _register(client, "held_buyer@test.com", club_name="Held Buyers FC")


@pytest_asyncio.fixture
async def seller(client: AsyncClient) -> dict:
    return await _register(client, "held_seller@test.com", club_name="Held Sellers FC")


async def _budget(db, transfer: int = 50_000_000, wage: int = 1_000_000):
    for f in (await db.execute(select(ClubFinance))).scalars():
        f.transfer_budget_total = Decimal(transfer)
        f.wage_budget_total_weekly = Decimal(wage)
    await db.commit()


async def _bid_terms(client, seller, fee=5_000_000) -> dict:
    player = await _create_player_for_seller(client, _auth_headers(seller))
    return {"player_id": player["id"], "to_club_id": await _get_club_id(client, _auth_headers(seller)),
            "fee_amount": fee, "wage_weekly": 20_000, "contract_years": 3}


async def _hold(client, club, kind, payload, ai=False):
    return await client.post("/lite/actions", json={"kind": kind, "payload": payload, "ai_assisted": ai},
                             headers=_auth_headers(club))


async def _run_due(db, action_id: str, after_seconds: int = 11):
    now = datetime.now(timezone.utc) + timedelta(seconds=after_seconds)
    return await held.execute_one(db, uuid.UUID(action_id), now)


async def _count(db, model, *where) -> int:
    return (await db.execute(select(func.count()).select_from(model).where(*where))).scalar_one()


async def _reserved(db, club_name: str) -> Decimal:
    from app.clubs.models import Club

    club = (await db.execute(select(Club).where(Club.name == club_name))).scalar_one()
    fin = (await db.execute(select(ClubFinance).where(ClubFinance.club_id == club.id))).scalar_one()
    await db.refresh(fin)
    return fin.transfer_reserved


# ── Held: nothing happens yet ─────────────────────────────────────────────────


async def test_a_held_bid_sends_nothing_until_its_window_closes(client: AsyncClient, db, buyer, seller):
    await _budget(db)
    terms = await _bid_terms(client, seller)
    resp = await _hold(client, buyer, "bid", terms)
    assert resp.status_code == 201, resp.text
    action = resp.json()
    assert action["status"] == "HELD"
    steps = action["progress"]["steps"]
    assert [s["label"] for s in steps][:2] == ["You approved it", "Bid sent"]
    assert steps[1]["state"] == "current" and steps[1]["hint"].startswith("Sending in ")
    assert action["progress"]["title"] == "Bid sent to Held Sellers FC"

    # Nothing exists for the other club: no offer, no notification, nothing reserved.
    assert await _count(db, Offer) == 0
    assert await _count(db, Notification) == 0
    assert await _reserved(db, "Held Buyers FC") == 0

    # Not yet due: the executor leaves it alone.
    assert await _run_due(db, action["id"], after_seconds=0) is None

    # Due: sent through the normal endpoint.
    assert await _run_due(db, action["id"]) == HeldActionStatus.EXECUTED
    assert await _count(db, Offer) == 1
    assert await _count(db, Notification) >= 1
    assert await _reserved(db, "Held Buyers FC") == Decimal("5000000")
    view = (await client.get(f"/lite/actions/{action['id']}", headers=_auth_headers(buyer))).json()
    assert view["status"] == "EXECUTED" and view["result"]["offer_id"]
    labels = [(s["label"], s["state"]) for s in view["progress"]["steps"]]
    assert ("Bid sent", "done") in labels and ("Waiting for Held Sellers FC to reply", "current") in labels

    late = await client.post(f"/lite/actions/{action['id']}/undo", headers=_auth_headers(buyer))
    assert late.status_code == 409


async def test_undo_before_send_leaves_no_trace_for_the_other_club(client: AsyncClient, db, buyer, seller):
    await _budget(db)
    action = (await _hold(client, buyer, "bid", await _bid_terms(client, seller))).json()
    resp = await client.post(f"/lite/actions/{action['id']}/undo", headers=_auth_headers(buyer))
    assert resp.status_code == 200 and resp.json()["status"] == "CANCELLED"
    assert resp.json()["progress"]["subline"] == "Nothing was sent."
    assert await _run_due(db, action["id"]) is None  # the executor skips it
    assert await _count(db, Offer) == 0
    seller_me = (await client.get("/auth/me", headers=_auth_headers(seller))).json()
    assert await _count(db, Notification, Notification.recipient_user_id == uuid.UUID(seller_me["id"])) == 0
    assert (await client.post(f"/lite/actions/{action['id']}/undo", headers=_auth_headers(buyer))).status_code == 409


# ── Checked at confirm time ───────────────────────────────────────────────────


async def test_problems_show_on_the_card_not_after_the_wait(client: AsyncClient, db, buyer, seller):
    await _budget(db, transfer=3_000_000)
    over = await _hold(client, buyer, "bid", await _bid_terms(client, seller, fee=5_000_000))
    assert over.status_code == 400 and "budget" in over.json()["detail"]

    await _budget(db)
    terms = await _bid_terms(client, seller)
    await client.post("/offers", json=terms, headers=_auth_headers(buyer))
    twice = await _hold(client, buyer, "bid", terms)
    assert twice.status_code == 409

    assert (await _hold(client, buyer, "dance", {})).status_code == 422
    assert await _count(db, HeldAction) == 0


async def test_only_the_side_whose_move_it_is_can_answer(client: AsyncClient, db, buyer, seller):
    await _budget(db)
    offer = (await client.post("/offers", json=await _bid_terms(client, seller), headers=_auth_headers(buyer))).json()
    # The buyer just sent it: not their move.
    resp = await _hold(client, buyer, "accept", {"offer_id": offer["id"]})
    assert resp.status_code == 409
    third = await _register(client, "held_third@test.com", club_name="Held Third FC")
    assert (await _hold(client, third, "reject", {"offer_id": offer["id"]})).status_code == 403
    assert (await _hold(client, seller, "counter", {"offer_id": offer["id"], "fee_amount": 0})).status_code == 400


# ── Answers: counter, accept, reject ──────────────────────────────────────────


async def test_a_held_counter_then_accept_runs_the_whole_path(client: AsyncClient, db, buyer, seller):
    await _budget(db)
    offer = (await client.post("/offers", json=await _bid_terms(client, seller), headers=_auth_headers(buyer))).json()
    counter = (await _hold(client, seller, "counter", {"offer_id": offer["id"], "fee_amount": 7_000_000})).json()
    assert counter["progress"]["title"] == "Counter sent to Held Buyers FC"
    assert await _run_due(db, counter["id"]) == HeldActionStatus.EXECUTED
    o = (await client.get(f"/offers/{offer['id']}", headers=_auth_headers(buyer))).json()
    assert o["status"] == "COUNTERED" and float(o["fee_amount"]) == 7_000_000

    # The buyer's progress for that offer is now "your turn".
    accept = (await _hold(client, buyer, "accept", {"offer_id": offer["id"]})).json()
    assert await _run_due(db, accept["id"]) == HeldActionStatus.EXECUTED
    view = (await client.get(f"/lite/actions/{accept['id']}", headers=_auth_headers(buyer))).json()
    assert view["result"]["deal_id"]
    states = {s["label"]: s["state"] for s in view["progress"]["steps"]}
    assert states["Fee agreed"] == "current" and states["Signed"] == "future"
    current = next(s for s in view["progress"]["steps"] if s["state"] == "current")
    assert current["hint"] == "Move the deal on to personal terms"  # the deal page's own next step

    progress = (await client.get(f"/lite/deals/{view['result']['deal_id']}/progress", headers=_auth_headers(seller))).json()
    assert [s["label"] for s in progress["steps"]] == ["Fee agreed", "Medical and personal terms", "Paperwork", "Signed"]


async def test_a_held_reject(client: AsyncClient, db, buyer, seller):
    await _budget(db)
    offer = (await client.post("/offers", json=await _bid_terms(client, seller), headers=_auth_headers(buyer))).json()
    action = (await _hold(client, seller, "reject", {"offer_id": offer["id"]})).json()
    assert await _run_due(db, action["id"]) == HeldActionStatus.EXECUTED
    o = (await client.get(f"/offers/{offer['id']}", headers=_auth_headers(seller))).json()
    assert o["status"] == "REJECTED"
    assert await _reserved(db, "Held Buyers FC") == 0


async def test_if_things_change_in_the_ten_seconds_the_send_fails_cleanly(client: AsyncClient, db, buyer, seller):
    await _budget(db)
    offer = (await client.post("/offers", json=await _bid_terms(client, seller), headers=_auth_headers(buyer))).json()
    action = (await _hold(client, seller, "accept", {"offer_id": offer["id"]})).json()
    # The buyer withdraws before the seller's acceptance goes out.
    assert (await client.post(f"/offers/{offer['id']}/withdraw", headers=_auth_headers(buyer))).status_code == 200
    assert await _run_due(db, action["id"]) == HeldActionStatus.FAILED
    view = (await client.get(f"/lite/actions/{action['id']}", headers=_auth_headers(seller))).json()
    assert view["status"] == "FAILED" and view["error"]
    assert view["progress"]["steps"][-1]["state"] == "ended"
    from app.deals.models import Deal
    assert await _count(db, Deal) == 0


# ── Approvals, permissions, privacy ───────────────────────────────────────────


async def test_a_managers_held_bid_over_the_threshold_waits_for_approval(client: AsyncClient, db, buyer, seller):
    from tests.test_approvals import _create_staff, _set_threshold

    await _budget(db)
    await _set_threshold(client, buyer, 1_000_000)
    manager = await _create_staff(client, db, _auth_headers(buyer), "held_mgr@test.com", "MANAGER")
    action = (await _hold(client, manager, "bid", await _bid_terms(client, seller))).json()
    assert await _run_due(db, action["id"]) == HeldActionStatus.EXECUTED
    view = (await client.get(f"/lite/actions/{action['id']}", headers=_auth_headers(manager))).json()
    assert view["result"]["approval_id"]
    assert view["progress"]["title"] == "Sent for approval"
    assert any(s["state"] == "current" and "approve" in s["label"] for s in view["progress"]["steps"])
    assert await _count(db, Offer) == 0  # nothing sent until approved


async def test_read_only_staff_cant_hold_and_no_one_else_can_see_or_undo(client: AsyncClient, db, buyer, seller):
    from tests.test_approvals import _create_staff

    await _budget(db)
    readonly = await _create_staff(client, db, _auth_headers(buyer), "held_ro@test.com", "READONLY")
    assert (await _hold(client, readonly, "bid", await _bid_terms(client, seller))).status_code == 403

    action = (await _hold(client, buyer, "bid", await _bid_terms(client, seller))).json()
    assert (await client.get(f"/lite/actions/{action['id']}", headers=_auth_headers(seller))).status_code == 404
    assert (await client.post(f"/lite/actions/{action['id']}/undo", headers=_auth_headers(seller))).status_code == 404


async def test_the_assistants_flag_reaches_the_sent_offer(client: AsyncClient, db, buyer, seller):
    from app.audit.models import AuditEvent

    await _budget(db)
    action = (await _hold(client, buyer, "bid", await _bid_terms(client, seller), ai=True)).json()
    await _run_due(db, action["id"])
    actions = (await db.execute(select(AuditEvent.action))).scalars().all()
    assert "AI_SUGGESTION_USED" in actions
    assert {"held_action.held", "held_action.executed"} <= set(actions)
