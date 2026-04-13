"""M4 — Deal lifecycle tests."""

from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import AsyncClient

from tests.conftest import _auth_headers, _register


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def buyer(client: AsyncClient) -> dict:
    return await _register(client, "buyer_deal@test.com", club_name="Deal Buyer FC")


@pytest_asyncio.fixture
async def seller(client: AsyncClient) -> dict:
    return await _register(client, "seller_deal@test.com", club_name="Deal Seller FC")


async def _give_budget(db, amount: Decimal = Decimal("100000000")):
    from app.clubs.models import ClubFinance
    from sqlalchemy import select

    result = await db.execute(select(ClubFinance))
    for f in result.scalars():
        f.transfer_budget_total = amount
    await db.commit()


async def _create_player_for_seller(client: AsyncClient, seller_headers: dict) -> dict:
    resp = await client.post("/players", json={"name": "Deal Player", "position": "FWD"}, headers=seller_headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _get_club_id(client: AsyncClient, headers: dict) -> str:
    resp = await client.get("/clubs/me", headers=headers)
    return resp.json()["id"]


async def _create_deal_via_offer(
    client: AsyncClient,
    buyer: dict,
    seller: dict,
    db,
    fee: float = 5_000_000,
) -> dict:
    """Create a deal by making and accepting an offer."""
    await _give_budget(db)
    sel_headers = _auth_headers(seller)
    buy_headers = _auth_headers(buyer)
    player = await _create_player_for_seller(client, sel_headers)
    seller_club_id = await _get_club_id(client, sel_headers)

    offer_resp = await client.post(
        "/offers",
        json={"player_id": player["id"], "to_club_id": seller_club_id, "fee_amount": fee},
        headers=buy_headers,
    )
    offer_id = offer_resp.json()["id"]

    deal_resp = await client.post(f"/offers/{offer_id}/accept", headers=sel_headers)
    assert deal_resp.status_code == 200, deal_resp.text
    return deal_resp.json()


async def _create_deal_via_bid(
    client: AsyncClient,
    buyer: dict,
    seller: dict,
    db,
) -> dict:
    """Create a deal by placing and accepting a bid on an auction."""
    await _give_budget(db)
    sel_headers = _auth_headers(seller)
    buy_headers = _auth_headers(buyer)
    player = await _create_player_for_seller(client, sel_headers)

    sale_resp = await client.post(
        "/sales",
        json={"player_id": player["id"], "sale_type": "AUCTION", "asking_price": 5_000_000},
        headers=sel_headers,
    )
    sale_id = sale_resp.json()["id"]

    bid_resp = await client.post(
        f"/sales/{sale_id}/bids", json={"amount": 5_000_000}, headers=buy_headers
    )
    bid_id = bid_resp.json()["id"]

    deal_resp = await client.post(f"/sales/{sale_id}/bids/{bid_id}/accept", headers=sel_headers)
    assert deal_resp.status_code == 200, deal_resp.text
    return deal_resp.json()


# ── Deal retrieval ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_deal_accessible_to_buyer(client: AsyncClient, buyer: dict, seller: dict, db):
    deal = await _create_deal_via_offer(client, buyer, seller, db)
    resp = await client.get(f"/deals/{deal['id']}", headers=_auth_headers(buyer))
    assert resp.status_code == 200
    assert resp.json()["status"] == "IN_PROGRESS"


@pytest.mark.asyncio
async def test_deal_accessible_to_seller(client: AsyncClient, buyer: dict, seller: dict, db):
    deal = await _create_deal_via_offer(client, buyer, seller, db)
    resp = await client.get(f"/deals/{deal['id']}", headers=_auth_headers(seller))
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_deal_list_for_club(client: AsyncClient, buyer: dict, seller: dict, db):
    await _create_deal_via_offer(client, buyer, seller, db)
    resp = await client.get("/deals", headers=_auth_headers(buyer))
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1


# ── Stage advancement ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_advance_agreement_to_paperwork(client: AsyncClient, buyer: dict, seller: dict, db):
    deal = await _create_deal_via_offer(client, buyer, seller, db)
    resp = await client.post(f"/deals/{deal['id']}/advance", headers=_auth_headers(buyer))
    assert resp.status_code == 200
    assert resp.json()["stage"] == "PAPERWORK"


@pytest.mark.asyncio
async def test_paperwork_stage_blocked_for_clubs(client: AsyncClient, buyer: dict, seller: dict, db):
    """Clubs cannot advance past PAPERWORK — only staff can."""
    deal = await _create_deal_via_offer(client, buyer, seller, db)

    # Advance to PAPERWORK
    await client.post(f"/deals/{deal['id']}/advance", headers=_auth_headers(buyer))

    # Try to advance again as club — should get 403
    resp = await client.post(f"/deals/{deal['id']}/advance", headers=_auth_headers(buyer))
    assert resp.status_code == 403
    assert "paperwork" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_full_stage_progression_via_staff(client: AsyncClient, buyer: dict, seller: dict, db):
    """Staff can complete all stages including PAPERWORK."""
    deal = await _create_deal_via_offer(client, buyer, seller, db)
    deal_id = deal["id"]

    # AGREEMENT → PAPERWORK (club can do)
    r = await client.post(f"/deals/{deal_id}/advance", headers=_auth_headers(buyer))
    assert r.json()["stage"] == "PAPERWORK"

    # Register an admin/superuser
    from app.auth.models import User
    from sqlalchemy import select

    result = await db.execute(select(User))
    for u in result.scalars():
        u.is_superuser = True
    await db.commit()

    # PAPERWORK → CONFIRMED (staff — use buyer who is now superuser)
    r = await client.post(f"/deals/{deal_id}/advance", headers=_auth_headers(buyer))
    assert r.json()["stage"] == "CONFIRMED"

    # CONFIRMED → COMPLETED
    r = await client.post(f"/deals/{deal_id}/advance", headers=_auth_headers(buyer))
    assert r.json()["stage"] == "COMPLETED"
    assert r.json()["status"] == "COMPLETED"


# ── Collapse deal ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_collapse_deal(client: AsyncClient, buyer: dict, seller: dict, db):
    deal = await _create_deal_via_offer(client, buyer, seller, db)
    resp = await client.post(f"/deals/{deal['id']}/collapse", headers=_auth_headers(buyer))
    assert resp.status_code == 200
    assert resp.json()["status"] == "COLLAPSED"


@pytest.mark.asyncio
async def test_cannot_collapse_completed_deal(client: AsyncClient, buyer: dict, seller: dict, db):
    deal = await _create_deal_via_offer(client, buyer, seller, db)

    # Make everyone superuser to complete the deal quickly
    from app.auth.models import User
    from sqlalchemy import select

    result = await db.execute(select(User))
    for u in result.scalars():
        u.is_superuser = True
    await db.commit()

    await client.post(f"/deals/{deal['id']}/staff/complete", headers=_auth_headers(buyer))
    resp = await client.post(f"/deals/{deal['id']}/collapse", headers=_auth_headers(buyer))
    assert resp.status_code == 400


# ── Deal notes ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_add_note_to_deal(client: AsyncClient, buyer: dict, seller: dict, db):
    deal = await _create_deal_via_offer(client, buyer, seller, db)
    resp = await client.post(
        f"/deals/{deal['id']}/notes",
        json={"body": "Awaiting medical clearance"},
        headers=_auth_headers(buyer),
    )
    assert resp.status_code == 201
    assert resp.json()["body"] == "Awaiting medical clearance"


@pytest.mark.asyncio
async def test_deal_notes_visible_in_detail(client: AsyncClient, buyer: dict, seller: dict, db):
    deal = await _create_deal_via_offer(client, buyer, seller, db)
    await client.post(
        f"/deals/{deal['id']}/notes",
        json={"body": "Note one"},
        headers=_auth_headers(buyer),
    )
    await client.post(
        f"/deals/{deal['id']}/notes",
        json={"body": "Note two"},
        headers=_auth_headers(seller),
    )
    resp = await client.get(f"/deals/{deal['id']}", headers=_auth_headers(buyer))
    assert len(resp.json()["deal_notes"]) == 2


# ── Staff endpoints ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_staff_complete_deal(client: AsyncClient, buyer: dict, seller: dict, db):
    deal = await _create_deal_via_offer(client, buyer, seller, db)

    from app.auth.models import User
    from sqlalchemy import select

    result = await db.execute(select(User))
    for u in result.scalars():
        u.is_superuser = True
    await db.commit()

    resp = await client.post(f"/deals/{deal['id']}/staff/complete", headers=_auth_headers(buyer))
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "COMPLETED"
    assert data["stage"] == "COMPLETED"


@pytest.mark.asyncio
async def test_non_staff_cannot_use_staff_endpoints(client: AsyncClient, buyer: dict, seller: dict, db):
    deal = await _create_deal_via_offer(client, buyer, seller, db)
    resp = await client.post(f"/deals/{deal['id']}/staff/complete", headers=_auth_headers(buyer))
    assert resp.status_code == 403


# ── Auction deal ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_auction_deal_is_flagged(client: AsyncClient, buyer: dict, seller: dict, db):
    deal = await _create_deal_via_bid(client, buyer, seller, db)
    resp = await client.get(f"/deals/{deal['id']}", headers=_auth_headers(buyer))
    assert resp.json()["is_auction_deal"] is True


@pytest.mark.asyncio
async def test_offer_deal_not_flagged_as_auction(client: AsyncClient, buyer: dict, seller: dict, db):
    deal = await _create_deal_via_offer(client, buyer, seller, db)
    resp = await client.get(f"/deals/{deal['id']}", headers=_auth_headers(buyer))
    assert resp.json()["is_auction_deal"] is False
