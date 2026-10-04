"""Phase 5 (club-team-roles spec) — spending-authority approval thresholds.

The D7 contract: MANAGER money actions ≥ threshold are captured (202, nothing
reserved, nothing executed); owner/SD are exempt; approval re-validates
everything fresh at execution; the status machine is one-way.
"""

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import AsyncClient

from tests.conftest import _auth_headers, _register
from tests.test_capabilities import _create_staff, _get_club_id, _give_budget


@pytest_asyncio.fixture
async def buyer(client: AsyncClient) -> dict:
    return await _register(client, "appr_buyer@test.com", club_name="Approval Buyers FC")


@pytest_asyncio.fixture
async def seller(client: AsyncClient) -> dict:
    return await _register(client, "appr_seller@test.com", club_name="Approval Sellers FC")


async def _set_threshold(client: AsyncClient, owner: dict, amount: float | None):
    resp = await client.patch(
        "/clubs/me/approval-policy",
        json={"approval_threshold": amount},
        headers=_auth_headers(owner),
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


async def _make_auction(client: AsyncClient, seller: dict, name: str = "Approval Player") -> str:
    headers = _auth_headers(seller)
    player = await client.post("/players", json={"name": name, "position": "FWD"}, headers=headers)
    assert player.status_code == 201, player.text
    sale = await client.post(
        "/sales",
        json={"player_id": player.json()["id"], "sale_type": "AUCTION", "asking_price": 1_000_000},
        headers=headers,
    )
    assert sale.status_code == 201, sale.text
    return sale.json()["id"]


async def _notif_types(client: AsyncClient, tokens: dict) -> list[str]:
    resp = await client.get("/notifications", headers=_auth_headers(tokens))
    return [n["type"] for n in resp.json()["items"]]


# ── Capture behaviour ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_manager_bid_at_or_over_threshold_captured_nothing_reserved(
    client: AsyncClient, db, buyer: dict, seller: dict
):
    await _give_budget(db)
    await _set_threshold(client, buyer, 5_000_000)
    sale_id = await _make_auction(client, seller)
    manager = await _create_staff(client, db, _auth_headers(buyer), "appr_mgr@test.com", "MANAGER")

    resp = await client.post(
        f"/sales/{sale_id}/bids", json={"amount": 6_000_000}, headers=_auth_headers(manager)
    )
    assert resp.status_code == 202, resp.text
    body = resp.json()
    assert body["status"] == "PENDING_APPROVAL"
    approval_id = body["approval_id"]

    # Nothing executed, nothing reserved (D7: an approval is an intent, not a hold)
    from sqlalchemy import select
    from app.clubs.models import ClubFinance
    from app.sales.models import Bid

    bids = (await db.execute(select(Bid))).scalars().all()
    assert bids == []
    buyer_club_id = await _get_club_id(client, _auth_headers(buyer))
    fin = (
        await db.execute(select(ClubFinance).where(ClubFinance.club_id == uuid.UUID(buyer_club_id)))
    ).scalar_one()
    assert fin.transfer_reserved == Decimal("0")

    # Owner and SD were notified of the request
    assert "APPROVAL_REQUESTED" in await _notif_types(client, buyer)

    # The requester sees their own request in the queue
    mine = await client.get("/clubs/me/approvals", headers=_auth_headers(manager))
    assert [a["id"] for a in mine.json()] == [approval_id]


@pytest.mark.asyncio
async def test_exactly_at_threshold_escalates(client: AsyncClient, db, buyer: dict, seller: dict):
    await _give_budget(db)
    await _set_threshold(client, buyer, 5_000_000)
    sale_id = await _make_auction(client, seller)
    manager = await _create_staff(client, db, _auth_headers(buyer), "appr_mgr_eq@test.com", "MANAGER")

    resp = await client.post(
        f"/sales/{sale_id}/bids", json={"amount": 5_000_000}, headers=_auth_headers(manager)
    )
    assert resp.status_code == 202, resp.text


@pytest.mark.asyncio
async def test_below_threshold_and_null_threshold_execute_directly(
    client: AsyncClient, db, buyer: dict, seller: dict
):
    await _give_budget(db)
    await _set_threshold(client, buyer, 5_000_000)
    sale_id = await _make_auction(client, seller)
    manager = await _create_staff(client, db, _auth_headers(buyer), "appr_mgr_lo@test.com", "MANAGER")

    resp = await client.post(
        f"/sales/{sale_id}/bids", json={"amount": 4_000_000}, headers=_auth_headers(manager)
    )
    assert resp.status_code == 201, resp.text

    # Clear the threshold — the feature disappears entirely
    await _set_threshold(client, buyer, None)
    resp = await client.post(
        f"/sales/{sale_id}/bids", json={"amount": 9_000_000}, headers=_auth_headers(manager)
    )
    assert resp.status_code == 201, resp.text


@pytest.mark.asyncio
async def test_owner_and_sd_are_exempt(client: AsyncClient, db, buyer: dict, seller: dict):
    await _give_budget(db)
    await _set_threshold(client, buyer, 5_000_000)
    sale_id = await _make_auction(client, seller)
    sd = await _create_staff(client, db, _auth_headers(buyer), "appr_sd@test.com", "SPORTING_DIRECTOR")

    resp = await client.post(
        f"/sales/{sale_id}/bids", json={"amount": 6_000_000}, headers=_auth_headers(sd)
    )
    assert resp.status_code == 201, resp.text

    resp = await client.post(
        f"/sales/{sale_id}/bids", json={"amount": 7_000_000}, headers=_auth_headers(buyer)
    )
    assert resp.status_code == 201, resp.text


# ── The full scenario-3 walkthrough ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_approve_executes_with_dual_attribution_and_seller_notified(
    client: AsyncClient, db, buyer: dict, seller: dict
):
    await _give_budget(db)
    await _set_threshold(client, buyer, 5_000_000)
    sale_id = await _make_auction(client, seller)
    manager = await _create_staff(client, db, _auth_headers(buyer), "appr_flow_mgr@test.com", "MANAGER")
    sd = await _create_staff(client, db, _auth_headers(buyer), "appr_flow_sd@test.com", "SPORTING_DIRECTOR")

    resp = await client.post(
        f"/sales/{sale_id}/bids", json={"amount": 6_000_000}, headers=_auth_headers(manager)
    )
    assert resp.status_code == 202
    approval_id = resp.json()["approval_id"]

    # SD sees it in the queue and approves
    queue = await client.get(
        "/clubs/me/approvals", params={"approval_status": "PENDING"}, headers=_auth_headers(sd)
    )
    assert [a["id"] for a in queue.json()] == [approval_id]

    resp = await client.post(f"/clubs/me/approvals/{approval_id}/approve", headers=_auth_headers(sd))
    assert resp.status_code == 200, resp.text
    decided = resp.json()
    assert decided["status"] == "APPROVED_EXECUTED"
    assert decided["requested_by_email"] == "appr_flow_mgr@test.com"
    assert decided["decided_by_user_id"] is not None
    assert decided["decided_by_user_id"] != decided["requested_by_user_id"]

    # The bid now exists for the buying club
    bids = await client.get(f"/sales/{sale_id}/bids", headers=_auth_headers(buyer))
    amounts = [b["amount"] for b in bids.json()]
    assert any(Decimal(a) == Decimal("6000000") for a in amounts)

    # Seller side notified normally; requester told of execution
    assert "AUCTION_BID_RECEIVED" in await _notif_types(client, seller)
    assert "APPROVAL_DECIDED" in await _notif_types(client, manager)


@pytest.mark.asyncio
async def test_stale_approval_fails_soft_when_sale_withdrawn(
    client: AsyncClient, db, buyer: dict, seller: dict
):
    """Auction closes between capture and approval → APPROVED_FAILED with
    reason, both parties notified, no 500 (D7 re-validation)."""
    await _give_budget(db)
    await _set_threshold(client, buyer, 5_000_000)
    sale_id = await _make_auction(client, seller)
    manager = await _create_staff(client, db, _auth_headers(buyer), "appr_stale_mgr@test.com", "MANAGER")
    sd = await _create_staff(client, db, _auth_headers(buyer), "appr_stale_sd@test.com", "SPORTING_DIRECTOR")

    resp = await client.post(
        f"/sales/{sale_id}/bids", json={"amount": 6_000_000}, headers=_auth_headers(manager)
    )
    approval_id = resp.json()["approval_id"]

    resp = await client.post(f"/sales/{sale_id}/withdraw", headers=_auth_headers(seller))
    assert resp.status_code == 200, resp.text

    resp = await client.post(f"/clubs/me/approvals/{approval_id}/approve", headers=_auth_headers(sd))
    assert resp.status_code == 200, resp.text
    decided = resp.json()
    assert decided["status"] == "APPROVED_FAILED"
    assert decided["failure_reason"]

    assert "APPROVAL_DECIDED" in await _notif_types(client, manager)
    assert "APPROVAL_DECIDED" in await _notif_types(client, sd)


# ── Status machine ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_status_machine_is_one_way(client: AsyncClient, db, buyer: dict, seller: dict):
    await _give_budget(db)
    await _set_threshold(client, buyer, 5_000_000)
    sale_id = await _make_auction(client, seller)
    manager = await _create_staff(client, db, _auth_headers(buyer), "appr_sm_mgr@test.com", "MANAGER")

    resp = await client.post(
        f"/sales/{sale_id}/bids", json={"amount": 6_000_000}, headers=_auth_headers(manager)
    )
    approval_id = resp.json()["approval_id"]

    resp = await client.post(f"/clubs/me/approvals/{approval_id}/approve", headers=_auth_headers(buyer))
    assert resp.status_code == 200

    # Second approve → 409; reject after decided → 409; cancel after decided → 409
    assert (
        await client.post(f"/clubs/me/approvals/{approval_id}/approve", headers=_auth_headers(buyer))
    ).status_code == 409
    assert (
        await client.post(
            f"/clubs/me/approvals/{approval_id}/reject", json={}, headers=_auth_headers(buyer)
        )
    ).status_code == 409
    assert (
        await client.post(f"/clubs/me/approvals/{approval_id}/cancel", headers=_auth_headers(manager))
    ).status_code == 409


@pytest.mark.asyncio
async def test_reject_and_cancel_paths(client: AsyncClient, db, buyer: dict, seller: dict):
    await _give_budget(db)
    await _set_threshold(client, buyer, 5_000_000)
    sale_id = await _make_auction(client, seller)
    manager = await _create_staff(client, db, _auth_headers(buyer), "appr_rc_mgr@test.com", "MANAGER")
    manager2 = await _create_staff(client, db, _auth_headers(buyer), "appr_rc_mgr2@test.com", "MANAGER")

    # Reject with reason → requester notified, nothing executed
    resp = await client.post(
        f"/sales/{sale_id}/bids", json={"amount": 6_000_000}, headers=_auth_headers(manager)
    )
    first_id = resp.json()["approval_id"]
    resp = await client.post(
        f"/clubs/me/approvals/{first_id}/reject",
        json={"reason": "Too rich for this window"},
        headers=_auth_headers(buyer),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "REJECTED"
    assert resp.json()["failure_reason"] == "Too rich for this window"
    assert "APPROVAL_DECIDED" in await _notif_types(client, manager)

    # A MANAGER cannot decide (no APPROVE_ACTIONS)
    resp = await client.post(
        f"/sales/{sale_id}/bids", json={"amount": 7_000_000}, headers=_auth_headers(manager)
    )
    second_id = resp.json()["approval_id"]
    assert (
        await client.post(f"/clubs/me/approvals/{second_id}/approve", headers=_auth_headers(manager2))
    ).status_code == 403

    # Only the requester can cancel their own
    assert (
        await client.post(f"/clubs/me/approvals/{second_id}/cancel", headers=_auth_headers(manager2))
    ).status_code == 403
    resp = await client.post(f"/clubs/me/approvals/{second_id}/cancel", headers=_auth_headers(manager))
    assert resp.status_code == 200
    assert resp.json()["status"] == "CANCELLED"


# ── Other actions + expiry + policy gating ────────────────────────────────────


@pytest.mark.asyncio
async def test_create_offer_capture_and_approve(client: AsyncClient, db, buyer: dict, seller: dict):
    await _give_budget(db)
    await _set_threshold(client, buyer, 5_000_000)
    manager = await _create_staff(client, db, _auth_headers(buyer), "appr_off_mgr@test.com", "MANAGER")

    player = await client.post(
        "/players", json={"name": "Offer Target", "position": "MID"}, headers=_auth_headers(seller)
    )
    seller_club_id = await _get_club_id(client, _auth_headers(seller))

    resp = await client.post(
        "/offers",
        json={
            "player_id": player.json()["id"],
            "to_club_id": seller_club_id,
            "fee_amount": 8_000_000,
        },
        headers=_auth_headers(manager),
    )
    assert resp.status_code == 202, resp.text
    approval_id = resp.json()["approval_id"]

    resp = await client.post(f"/clubs/me/approvals/{approval_id}/approve", headers=_auth_headers(buyer))
    assert resp.status_code == 200
    assert resp.json()["status"] == "APPROVED_EXECUTED"

    sent = await client.get("/offers/sent", headers=_auth_headers(buyer))
    fees = [o["fee_amount"] for o in sent.json()["items"]]
    assert any(Decimal(f) == Decimal("8000000") for f in fees)
    assert "OFFER_RECEIVED" in await _notif_types(client, seller)


@pytest.mark.asyncio
async def test_seller_side_accept_bid_capture(client: AsyncClient, db, buyer: dict, seller: dict):
    """ACCEPT_BID is threshold-gated on the *seller* club's manager."""
    await _give_budget(db)
    await _set_threshold(client, seller, 5_000_000)
    sale_id = await _make_auction(client, seller)
    resp = await client.post(
        f"/sales/{sale_id}/bids", json={"amount": 6_000_000}, headers=_auth_headers(buyer)
    )
    bid_id = resp.json()["id"]
    sel_manager = await _create_staff(client, db, _auth_headers(seller), "appr_selmgr@test.com", "MANAGER")

    resp = await client.post(
        f"/sales/{sale_id}/bids/{bid_id}/accept", headers=_auth_headers(sel_manager)
    )
    assert resp.status_code == 202, resp.text
    approval_id = resp.json()["approval_id"]

    resp = await client.post(f"/clubs/me/approvals/{approval_id}/approve", headers=_auth_headers(seller))
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "APPROVED_EXECUTED"
    assert "AUCTION_BID_ACCEPTED" in await _notif_types(client, buyer)


@pytest.mark.asyncio
async def test_expiry_job_expires_and_notifies(client: AsyncClient, db, buyer: dict, seller: dict):
    from sqlalchemy import select
    from app.approvals.models import PendingApproval
    from app.approvals.service import expire_stale_approvals

    await _give_budget(db)
    await _set_threshold(client, buyer, 5_000_000)
    sale_id = await _make_auction(client, seller)
    manager = await _create_staff(client, db, _auth_headers(buyer), "appr_exp_mgr@test.com", "MANAGER")

    resp = await client.post(
        f"/sales/{sale_id}/bids", json={"amount": 6_000_000}, headers=_auth_headers(manager)
    )
    assert resp.status_code == 202

    approval = (await db.execute(select(PendingApproval))).scalars().one()
    approval.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
    await db.commit()

    count = await expire_stale_approvals(db)
    await db.commit()
    assert count == 1
    await db.refresh(approval)
    assert approval.status.value == "EXPIRED"
    assert "APPROVAL_DECIDED" in await _notif_types(client, manager)


@pytest.mark.asyncio
async def test_policy_endpoint_is_team_manage_only(client: AsyncClient, db, buyer: dict):
    sd = await _create_staff(client, db, _auth_headers(buyer), "appr_pol_sd@test.com", "SPORTING_DIRECTOR")
    resp = await client.patch(
        "/clubs/me/approval-policy",
        json={"approval_threshold": 1_000_000},
        headers=_auth_headers(sd),
    )
    assert resp.status_code == 403

    data = await _set_threshold(client, buyer, 1_000_000)
    assert Decimal(data["approval_threshold"]) == Decimal("1000000")
    resp = await client.get("/clubs/me/approval-policy", headers=_auth_headers(buyer))
    assert Decimal(resp.json()["approval_threshold"]) == Decimal("1000000")


# ── Loans and anonymity through the approval path ────────────────────────────


async def _loanable_player(client: AsyncClient, db, seller: dict, name: str) -> tuple[str, str]:
    """A seller-owned player under contract, so a loan can be validated against
    his parent contract. Returns (player_id, seller_club_id)."""
    from datetime import date

    from tests.test_offers import _contract, _give_wage_budget

    await _give_budget(db)
    await _give_wage_budget(db)
    player = await client.post(
        "/players", json={"name": name, "position": "MID"}, headers=_auth_headers(seller)
    )
    assert player.status_code == 201, player.text
    seller_club_id = await _get_club_id(client, _auth_headers(seller))
    await _contract(db, player.json()["id"], seller_club_id, date(2028, 6, 30))
    return player.json()["id"], seller_club_id


@pytest.mark.asyncio
async def test_loan_with_obligation_is_escalated_and_replayed_as_a_loan(
    client: AsyncClient, db, buyer: dict, seller: dict
):
    """A loan carries no transfer fee, so the threshold used to see £0 and let
    it through. The commitment is the loan fee plus the obligation price — and
    the approved replay must create the same loan, not a permanent offer."""
    from tests.test_offers import _loan_body

    player_id, seller_club_id = await _loanable_player(client, db, seller, "Loan Approval")
    await _set_threshold(client, buyer, 10_000_000)
    manager = await _create_staff(client, db, _auth_headers(buyer), "appr_loan_mgr@test.com", "MANAGER")

    body = _loan_body(
        player_id, seller_club_id, option_to_buy=18_000_000, obligation_to_buy=True,
        recall_allowed=True,
    )
    resp = await client.post("/offers", json=body, headers=_auth_headers(manager))
    assert resp.status_code == 202, resp.text
    approval_id = resp.json()["approval_id"]

    pending = await client.get("/clubs/me/approvals", headers=_auth_headers(buyer))
    row = next(a for a in pending.json() if a["id"] == approval_id)
    assert Decimal(str(row["amount"])) == Decimal("20000000")  # £2m fee + £18m obligation
    assert "loan" in row["summary"] and "obligation to buy" in row["summary"]

    resp = await client.post(f"/clubs/me/approvals/{approval_id}/approve", headers=_auth_headers(buyer))
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "APPROVED_EXECUTED"

    offer = (await client.get("/offers/sent", headers=_auth_headers(buyer))).json()["items"][0]
    assert offer["deal_type"] == "LOAN"
    assert offer["fee_amount"] is None
    assert Decimal(str(offer["loan_fee"])) == Decimal("2000000")
    assert Decimal(str(offer["option_to_buy"])) == Decimal("18000000")
    assert offer["obligation_to_buy"] is True
    assert offer["recall_allowed"] is True
    assert Decimal(str(offer["wage_split_pct"])) == Decimal("0.6")
    assert offer["loan_end"] == "2027-05-31"


@pytest.mark.asyncio
async def test_loan_option_alone_is_not_counted(client: AsyncClient, db, buyer: dict, seller: dict):
    """An option is a right, not a commitment: a £2m loan with an £18m option
    stays under a £10m threshold and executes directly."""
    from tests.test_offers import _loan_body

    player_id, seller_club_id = await _loanable_player(client, db, seller, "Loan Option")
    await _set_threshold(client, buyer, 10_000_000)
    manager = await _create_staff(client, db, _auth_headers(buyer), "appr_opt_mgr@test.com", "MANAGER")

    body = _loan_body(player_id, seller_club_id, option_to_buy=18_000_000)
    resp = await client.post("/offers", json=body, headers=_auth_headers(manager))
    assert resp.status_code == 201, resp.text


@pytest.mark.asyncio
async def test_seller_manager_accepting_a_loan_obligation_is_escalated(
    client: AsyncClient, db, buyer: dict, seller: dict
):
    """Agreeing to an obligation is agreeing to sell at that price."""
    from tests.test_offers import _loan_body

    player_id, seller_club_id = await _loanable_player(client, db, seller, "Loan Accept")
    body = _loan_body(player_id, seller_club_id, option_to_buy=18_000_000, obligation_to_buy=True)
    offer = await client.post("/offers", json=body, headers=_auth_headers(buyer))
    assert offer.status_code == 201, offer.text

    await _set_threshold(client, seller, 10_000_000)
    sel_manager = await _create_staff(client, db, _auth_headers(seller), "appr_loan_sel@test.com", "MANAGER")
    resp = await client.post(f"/offers/{offer.json()['id']}/accept", headers=_auth_headers(sel_manager))
    assert resp.status_code == 202, resp.text


@pytest.mark.asyncio
async def test_approved_anonymous_offer_stays_anonymous(
    client: AsyncClient, db, buyer: dict, seller: dict
):
    """The replay used to drop is_anonymous, so approving an anonymous offer
    sent it to the seller with the buyer named."""
    await _give_budget(db)
    await _set_threshold(client, buyer, 5_000_000)
    manager = await _create_staff(client, db, _auth_headers(buyer), "appr_anon_mgr@test.com", "MANAGER")
    player = await client.post(
        "/players", json={"name": "Anon Target", "position": "MID"}, headers=_auth_headers(seller)
    )
    seller_club_id = await _get_club_id(client, _auth_headers(seller))
    buyer_club_id = await _get_club_id(client, _auth_headers(buyer))

    resp = await client.post(
        "/offers",
        json={
            "player_id": player.json()["id"], "to_club_id": seller_club_id,
            "fee_amount": 8_000_000, "is_anonymous": True,
        },
        headers=_auth_headers(manager),
    )
    assert resp.status_code == 202, resp.text
    resp = await client.post(
        f"/clubs/me/approvals/{resp.json()['approval_id']}/approve", headers=_auth_headers(buyer)
    )
    assert resp.json()["status"] == "APPROVED_EXECUTED"

    received = await client.get("/offers/received", headers=_auth_headers(seller))
    assert received.json()["items"][0]["is_anonymous"] is True
    assert buyer_club_id not in received.text


@pytest.mark.asyncio
async def test_approved_zero_fee_offer_replays_without_crashing(
    client: AsyncClient, db, buyer: dict, seller: dict
):
    """A missing fee was stored as the string "None", which the replay's
    Decimal() could not parse. Fees are now always named, £0 included, and
    older payloads are still read (see _dec in approvals/service.py)."""
    await _give_budget(db)
    await _set_threshold(client, buyer, 0)
    manager = await _create_staff(client, db, _auth_headers(buyer), "appr_nofee_mgr@test.com", "MANAGER")
    player = await client.post(
        "/players", json={"name": "No Fee Target", "position": "MID"}, headers=_auth_headers(seller)
    )
    seller_club_id = await _get_club_id(client, _auth_headers(seller))

    resp = await client.post(
        "/offers",
        json={
            "player_id": player.json()["id"], "to_club_id": seller_club_id,
            "fee_amount": 0, "no_fee_reason": "Release to clear wages",
        },
        headers=_auth_headers(manager),
    )
    assert resp.status_code == 202, resp.text
    resp = await client.post(
        f"/clubs/me/approvals/{resp.json()['approval_id']}/approve", headers=_auth_headers(buyer)
    )
    assert resp.json()["status"] == "APPROVED_EXECUTED", resp.text

    # The reason survives the replay, as it must for the seller to read it.
    received = (await client.get("/offers/received", headers=_auth_headers(seller))).json()["items"][0]
    assert any("clear wages" in m["body"] for m in received["messages"])


# ── The approval decision sheet (notifications phase 4 follow-up) ─────────────


@pytest.mark.asyncio
async def test_one_approval_for_its_decision_sheet(client: AsyncClient, db, buyer: dict, seller: dict):
    await _give_budget(db)
    await _set_threshold(client, buyer, 5_000_000)
    sale_id = await _make_auction(client, seller, name="Sheet Player")
    manager = await _create_staff(client, db, _auth_headers(buyer), "appr_sheet_mgr@test.com", "MANAGER")
    resp = await client.post(f"/sales/{sale_id}/bids", json={"amount": 6_000_000}, headers=_auth_headers(manager))
    approval_id = resp.json()["approval_id"]

    sheet = (await client.get(f"/clubs/me/approvals/{approval_id}", headers=_auth_headers(buyer))).json()
    assert sheet["player_name"] == "Sheet Player" and float(sheet["amount"]) == 6_000_000
    assert sheet["budget_after"] is not None
    # The requester sees their own; another club never does.
    assert (await client.get(f"/clubs/me/approvals/{approval_id}", headers=_auth_headers(manager))).status_code == 200
    assert (await client.get(f"/clubs/me/approvals/{approval_id}", headers=_auth_headers(seller))).status_code == 404
    # The approver's notification opens this approval.
    from sqlalchemy import select

    from app.notifications.models import Notification, NotificationType

    n = (await db.execute(select(Notification).where(Notification.type == NotificationType.APPROVAL_REQUESTED))).scalars().first()
    assert n.link == f"/club/approvals?id={approval_id}"
