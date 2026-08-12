"""B2 — Dashboard aggregate endpoint tests."""

import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient

from tests.conftest import _auth_headers, _register
from tests.test_approvals import _make_auction, _set_threshold
from tests.test_capabilities import _create_staff, _give_budget


@pytest_asyncio.fixture
async def buyer(client: AsyncClient) -> dict:
    return await _register(client, "dash_buyer@test.com", club_name="Dashboard Buyer FC")


@pytest_asyncio.fixture
async def seller(client: AsyncClient) -> dict:
    return await _register(client, "dash_seller@test.com", club_name="Dashboard Seller FC")


async def _create_player_for_seller(client: AsyncClient, seller_headers: dict) -> dict:
    resp = await client.post("/players", json={"name": "Dashboard Player", "position": "FWD"}, headers=seller_headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _get_club_id(client: AsyncClient, headers: dict) -> str:
    resp = await client.get("/clubs/me", headers=headers)
    return resp.json()["id"]


async def _set_deal(db, deal_id: str, **fields) -> None:
    from sqlalchemy import select

    from app.deals.models import Deal

    result = await db.execute(select(Deal).where(Deal.id == uuid.UUID(deal_id)))
    deal = result.scalar_one()
    for key, value in fields.items():
        setattr(deal, key, value)
    await db.commit()


@pytest.mark.asyncio
async def test_dashboard_requires_auth(client: AsyncClient):
    resp = await client.get("/clubs/me/dashboard")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_dashboard_empty_for_fresh_club(client: AsyncClient, buyer: dict):
    resp = await client.get("/clubs/me/dashboard", headers=_auth_headers(buyer))
    assert resp.status_code == 200
    assert resp.json()["waiting_on_you"] == []


@pytest.mark.asyncio
async def test_dashboard_shows_offer_only_to_recipient(client: AsyncClient, buyer: dict, seller: dict, db):
    await _give_budget(db)
    buy_headers = _auth_headers(buyer)
    sel_headers = _auth_headers(seller)
    player = await _create_player_for_seller(client, sel_headers)
    seller_club_id = await _get_club_id(client, sel_headers)

    resp = await client.post(
        "/offers",
        json={"player_id": player["id"], "to_club_id": seller_club_id, "fee_amount": 5_000_000},
        headers=buy_headers,
    )
    assert resp.status_code == 201, resp.text
    offer_id = resp.json()["id"]

    seller_dash = await client.get("/clubs/me/dashboard", headers=sel_headers)
    items = seller_dash.json()["waiting_on_you"]
    assert [i for i in items if i["kind"] == "offer" and i["id"] == offer_id]

    # The buyer just sent it themselves — it's the seller's move, not theirs.
    buyer_dash = await client.get("/clubs/me/dashboard", headers=buy_headers)
    assert buyer_dash.json()["waiting_on_you"] == []


@pytest.mark.asyncio
async def test_dashboard_shows_confirmed_deal_to_both_parties(client: AsyncClient, buyer: dict, seller: dict, db):
    from app.deals.models import DealStage

    await _give_budget(db)
    buy_headers = _auth_headers(buyer)
    sel_headers = _auth_headers(seller)
    player = await _create_player_for_seller(client, sel_headers)
    seller_club_id = await _get_club_id(client, sel_headers)

    offer_resp = await client.post(
        "/offers",
        json={"player_id": player["id"], "to_club_id": seller_club_id, "fee_amount": 5_000_000},
        headers=buy_headers,
    )
    offer_id = offer_resp.json()["id"]
    deal_resp = await client.post(f"/offers/{offer_id}/accept", headers=sel_headers)
    assert deal_resp.status_code == 200, deal_resp.text
    deal_id = deal_resp.json()["id"]

    await _set_deal(db, deal_id, stage=DealStage.CONFIRMED)

    for headers in (buy_headers, sel_headers):
        dash = await client.get("/clubs/me/dashboard", headers=headers)
        items = dash.json()["waiting_on_you"]
        match = [i for i in items if i["kind"] == "deal" and i["id"] == deal_id]
        assert match, dash.json()
        assert match[0]["reason"] == "You — signature"


@pytest.mark.asyncio
async def test_dashboard_shows_pending_approval_to_owner(client: AsyncClient, db, buyer: dict, seller: dict):
    await _give_budget(db)
    await _set_threshold(client, buyer, 5_000_000)
    sale_id = await _make_auction(client, seller)
    manager = await _create_staff(client, db, _auth_headers(buyer), "dash_mgr@test.com", "MANAGER")

    resp = await client.post(
        f"/sales/{sale_id}/bids", json={"amount": 6_000_000}, headers=_auth_headers(manager)
    )
    assert resp.status_code == 202, resp.text
    approval_id = resp.json()["approval_id"]

    dash = await client.get("/clubs/me/dashboard", headers=_auth_headers(buyer))
    items = dash.json()["waiting_on_you"]
    assert [i for i in items if i["kind"] == "approval" and i["id"] == approval_id]
