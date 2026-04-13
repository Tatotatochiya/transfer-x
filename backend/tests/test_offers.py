"""M4 — Offer negotiation tests."""

from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import AsyncClient

from tests.conftest import _auth_headers, _register


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def buyer(client: AsyncClient) -> dict:
    return await _register(client, "buyer_offer@test.com", club_name="Buyer FC")


@pytest_asyncio.fixture
async def seller(client: AsyncClient) -> dict:
    return await _register(client, "seller_offer@test.com", club_name="Seller FC")


@pytest_asyncio.fixture
async def third_club(client: AsyncClient) -> dict:
    return await _register(client, "third_offer@test.com", club_name="Third FC")


async def _create_player(client: AsyncClient, headers: dict, name: str = "Offer Player") -> dict:
    resp = await client.post("/players", json={"name": name, "position": "MID"}, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _give_budget(db, amount: Decimal = Decimal("50000000")):
    from app.clubs.models import ClubFinance
    from sqlalchemy import select

    result = await db.execute(select(ClubFinance))
    for f in result.scalars():
        f.transfer_budget_total = amount
    await db.commit()


async def _make_offer(
    client: AsyncClient,
    headers: dict,
    player_id: str,
    to_club_id: str | None,
    fee: float = 5_000_000,
) -> dict:
    body = {"player_id": player_id, "fee_amount": fee}
    if to_club_id:
        body["to_club_id"] = to_club_id
    resp = await client.post("/offers", json=body, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _get_seller_club_id(client: AsyncClient, seller_headers: dict) -> str:
    resp = await client.get("/clubs/me", headers=seller_headers)
    assert resp.status_code == 200
    return resp.json()["id"]


# ── Create offer ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_offer_requires_auth(client: AsyncClient, seller: dict):
    headers = _auth_headers(seller)
    player = await _create_player(client, headers)
    resp = await client.post("/offers", json={"player_id": player["id"], "fee_amount": 5_000_000})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_create_offer_no_budget_fails(client: AsyncClient, buyer: dict, seller: dict):
    sel_headers = _auth_headers(seller)
    player = await _create_player(client, sel_headers)
    seller_club_id = await _get_seller_club_id(client, sel_headers)

    resp = await client.post(
        "/offers",
        json={"player_id": player["id"], "to_club_id": seller_club_id, "fee_amount": 5_000_000},
        headers=_auth_headers(buyer),
    )
    assert resp.status_code == 400
    assert "budget" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_create_offer_success(client: AsyncClient, buyer: dict, seller: dict, db):
    await _give_budget(db)
    sel_headers = _auth_headers(seller)
    player = await _create_player(client, sel_headers)
    seller_club_id = await _get_seller_club_id(client, sel_headers)

    resp = await client.post(
        "/offers",
        json={"player_id": player["id"], "to_club_id": seller_club_id, "fee_amount": 5_000_000},
        headers=_auth_headers(buyer),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "SENT"
    assert float(data["fee_amount"]) == 5_000_000
    # Events should have CREATED + SENT
    assert len(data["events"]) == 2


@pytest.mark.asyncio
async def test_offer_visible_to_both_parties(client: AsyncClient, buyer: dict, seller: dict, db):
    await _give_budget(db)
    sel_headers = _auth_headers(seller)
    buy_headers = _auth_headers(buyer)
    player = await _create_player(client, sel_headers)
    seller_club_id = await _get_seller_club_id(client, sel_headers)

    offer = await _make_offer(client, buy_headers, player["id"], seller_club_id)

    # Both can view it
    assert (await client.get(f"/offers/{offer['id']}", headers=buy_headers)).status_code == 200
    assert (await client.get(f"/offers/{offer['id']}", headers=sel_headers)).status_code == 200


@pytest.mark.asyncio
async def test_offer_not_visible_to_third_party(client: AsyncClient, buyer: dict, seller: dict, third_club: dict, db):
    await _give_budget(db)
    sel_headers = _auth_headers(seller)
    player = await _create_player(client, sel_headers)
    seller_club_id = await _get_seller_club_id(client, sel_headers)

    offer = await _make_offer(client, _auth_headers(buyer), player["id"], seller_club_id)

    resp = await client.get(f"/offers/{offer['id']}", headers=_auth_headers(third_club))
    assert resp.status_code == 403


# ── Counter offer ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_counter_offer(client: AsyncClient, buyer: dict, seller: dict, db):
    await _give_budget(db)
    sel_headers = _auth_headers(seller)
    buy_headers = _auth_headers(buyer)
    player = await _create_player(client, sel_headers)
    seller_club_id = await _get_seller_club_id(client, sel_headers)

    offer = await _make_offer(client, buy_headers, player["id"], seller_club_id)

    resp = await client.post(
        f"/offers/{offer['id']}/counter",
        json={"fee_amount": 8_000_000},
        headers=sel_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "COUNTERED"
    assert float(data["fee_amount"]) == 8_000_000


@pytest.mark.asyncio
async def test_third_party_cannot_counter(client: AsyncClient, buyer: dict, seller: dict, third_club: dict, db):
    await _give_budget(db)
    sel_headers = _auth_headers(seller)
    player = await _create_player(client, sel_headers)
    seller_club_id = await _get_seller_club_id(client, sel_headers)

    offer = await _make_offer(client, _auth_headers(buyer), player["id"], seller_club_id)

    resp = await client.post(
        f"/offers/{offer['id']}/counter",
        json={"fee_amount": 6_000_000},
        headers=_auth_headers(third_club),
    )
    assert resp.status_code == 400


# ── Accept offer ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_accept_offer_creates_deal(client: AsyncClient, buyer: dict, seller: dict, db):
    await _give_budget(db)
    sel_headers = _auth_headers(seller)
    buy_headers = _auth_headers(buyer)
    player = await _create_player(client, sel_headers)
    seller_club_id = await _get_seller_club_id(client, sel_headers)

    offer = await _make_offer(client, buy_headers, player["id"], seller_club_id)

    resp = await client.post(f"/offers/{offer['id']}/accept", headers=sel_headers)
    assert resp.status_code == 200
    deal = resp.json()
    assert deal["status"] == "IN_PROGRESS"
    assert deal["stage"] == "AGREEMENT"
    assert float(deal["agreed_fee"]) == 5_000_000

    # Offer should now be ACCEPTED
    offer_resp = await client.get(f"/offers/{offer['id']}", headers=buy_headers)
    assert offer_resp.json()["status"] == "ACCEPTED"


@pytest.mark.asyncio
async def test_cannot_accept_already_accepted(client: AsyncClient, buyer: dict, seller: dict, db):
    await _give_budget(db)
    sel_headers = _auth_headers(seller)
    player = await _create_player(client, sel_headers)
    seller_club_id = await _get_seller_club_id(client, sel_headers)

    offer = await _make_offer(client, _auth_headers(buyer), player["id"], seller_club_id)
    await client.post(f"/offers/{offer['id']}/accept", headers=sel_headers)

    resp = await client.post(f"/offers/{offer['id']}/accept", headers=sel_headers)
    assert resp.status_code == 400


# ── Reject offer ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_reject_offer(client: AsyncClient, buyer: dict, seller: dict, db):
    await _give_budget(db)
    sel_headers = _auth_headers(seller)
    player = await _create_player(client, sel_headers)
    seller_club_id = await _get_seller_club_id(client, sel_headers)

    offer = await _make_offer(client, _auth_headers(buyer), player["id"], seller_club_id)

    resp = await client.post(f"/offers/{offer['id']}/reject", headers=sel_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "REJECTED"

    # Budget should be released
    from app.clubs.models import ClubFinance
    from sqlalchemy import select as sa_select

    result = await db.execute(sa_select(ClubFinance))
    for f in result.scalars():
        await db.refresh(f)
        assert f.transfer_reserved == Decimal("0")


# ── Withdraw offer ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_withdraw_own_offer(client: AsyncClient, buyer: dict, seller: dict, db):
    await _give_budget(db)
    sel_headers = _auth_headers(seller)
    buy_headers = _auth_headers(buyer)
    player = await _create_player(client, sel_headers)
    seller_club_id = await _get_seller_club_id(client, sel_headers)

    offer = await _make_offer(client, buy_headers, player["id"], seller_club_id)

    resp = await client.post(f"/offers/{offer['id']}/withdraw", headers=buy_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "WITHDRAWN"


@pytest.mark.asyncio
async def test_receiver_cannot_withdraw(client: AsyncClient, buyer: dict, seller: dict, db):
    await _give_budget(db)
    sel_headers = _auth_headers(seller)
    player = await _create_player(client, sel_headers)
    seller_club_id = await _get_seller_club_id(client, sel_headers)

    offer = await _make_offer(client, _auth_headers(buyer), player["id"], seller_club_id)

    resp = await client.post(f"/offers/{offer['id']}/withdraw", headers=sel_headers)
    assert resp.status_code == 400
    assert "sender" in resp.json()["detail"].lower()


# ── Messages ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_add_message_to_offer(client: AsyncClient, buyer: dict, seller: dict, db):
    await _give_budget(db)
    sel_headers = _auth_headers(seller)
    buy_headers = _auth_headers(buyer)
    player = await _create_player(client, sel_headers)
    seller_club_id = await _get_seller_club_id(client, sel_headers)

    offer = await _make_offer(client, buy_headers, player["id"], seller_club_id)

    resp = await client.post(
        f"/offers/{offer['id']}/messages",
        json={"body": "Very interested in this player!"},
        headers=buy_headers,
    )
    assert resp.status_code == 201
    assert resp.json()["body"] == "Very interested in this player!"

    # Verify message appears in offer detail
    offer_resp = await client.get(f"/offers/{offer['id']}", headers=buy_headers)
    assert len(offer_resp.json()["messages"]) == 1


@pytest.mark.asyncio
async def test_cannot_message_closed_offer(client: AsyncClient, buyer: dict, seller: dict, db):
    await _give_budget(db)
    sel_headers = _auth_headers(seller)
    buy_headers = _auth_headers(buyer)
    player = await _create_player(client, sel_headers)
    seller_club_id = await _get_seller_club_id(client, sel_headers)

    offer = await _make_offer(client, buy_headers, player["id"], seller_club_id)
    await client.post(f"/offers/{offer['id']}/reject", headers=sel_headers)

    resp = await client.post(
        f"/offers/{offer['id']}/messages",
        json={"body": "Can we reconsider?"},
        headers=buy_headers,
    )
    assert resp.status_code == 400


# ── List offers ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_sent_offers(client: AsyncClient, buyer: dict, seller: dict, db):
    await _give_budget(db)
    sel_headers = _auth_headers(seller)
    buy_headers = _auth_headers(buyer)
    player = await _create_player(client, sel_headers)
    seller_club_id = await _get_seller_club_id(client, sel_headers)

    await _make_offer(client, buy_headers, player["id"], seller_club_id)

    resp = await client.get("/offers/sent", headers=buy_headers)
    assert resp.status_code == 200
    assert resp.json()["total"] == 1


@pytest.mark.asyncio
async def test_list_received_offers(client: AsyncClient, buyer: dict, seller: dict, db):
    await _give_budget(db)
    sel_headers = _auth_headers(seller)
    player = await _create_player(client, sel_headers)
    seller_club_id = await _get_seller_club_id(client, sel_headers)

    await _make_offer(client, _auth_headers(buyer), player["id"], seller_club_id)

    resp = await client.get("/offers/received", headers=sel_headers)
    assert resp.status_code == 200
    assert resp.json()["total"] == 1
