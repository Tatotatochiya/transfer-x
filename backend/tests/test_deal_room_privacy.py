"""Item 8 — private per-club channels in the deal room."""

from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import AsyncClient

from tests.conftest import _auth_headers, _register

pytestmark = pytest.mark.asyncio


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def buyer(client: AsyncClient) -> dict:
    return await _register(client, "room_buyer@test.com", club_name="Room Buyer FC")


@pytest_asyncio.fixture
async def seller(client: AsyncClient) -> dict:
    return await _register(client, "room_seller@test.com", club_name="Room Seller FC")


async def _give_budget(db, amount: Decimal = Decimal("100000000")):
    from app.clubs.models import ClubFinance
    from sqlalchemy import select

    result = await db.execute(select(ClubFinance))
    for f in result.scalars():
        f.transfer_budget_total = amount
    await db.commit()


async def _create_deal(client: AsyncClient, buyer: dict, seller: dict, db) -> dict:
    await _give_budget(db)
    sel_headers = _auth_headers(seller)
    buy_headers = _auth_headers(buyer)

    player_resp = await client.post(
        "/players", json={"name": "Room Player", "position": "MID"}, headers=sel_headers,
    )
    player = player_resp.json()
    seller_club_id = (await client.get("/clubs/me", headers=sel_headers)).json()["id"]

    offer_resp = await client.post(
        "/offers",
        json={"player_id": player["id"], "to_club_id": seller_club_id, "fee_amount": 5_000_000},
        headers=buy_headers,
    )
    offer_id = offer_resp.json()["id"]

    deal_resp = await client.post(f"/offers/{offer_id}/accept", headers=sel_headers)
    assert deal_resp.status_code == 200, deal_resp.text
    return deal_resp.json()


# ── Comments ──────────────────────────────────────────────────────────────────


async def test_default_comment_is_shared_and_visible_to_both(
    client: AsyncClient, buyer: dict, seller: dict, db
):
    deal = await _create_deal(client, buyer, seller, db)
    buy_headers, sel_headers = _auth_headers(buyer), _auth_headers(seller)

    resp = await client.post(f"/deals/{deal['id']}/comments", json={"body": "hello"}, headers=buy_headers)
    assert resp.status_code == 201, resp.text
    assert resp.json()["audience"] == "SHARED"

    seller_view = await client.get(f"/deals/{deal['id']}/comments", headers=sel_headers)
    assert any(c["body"] == "hello" for c in seller_view.json())


async def test_buyer_private_comment_hidden_from_seller(
    client: AsyncClient, buyer: dict, seller: dict, db
):
    deal = await _create_deal(client, buyer, seller, db)
    buy_headers, sel_headers = _auth_headers(buyer), _auth_headers(seller)

    resp = await client.post(
        f"/deals/{deal['id']}/comments",
        json={"body": "buyer internal note", "audience": "BUYER_ONLY"},
        headers=buy_headers,
    )
    assert resp.status_code == 201, resp.text

    seller_view = await client.get(f"/deals/{deal['id']}/comments", headers=sel_headers)
    assert not any(c["body"] == "buyer internal note" for c in seller_view.json())

    buyer_view = await client.get(f"/deals/{deal['id']}/comments", headers=buy_headers)
    assert any(c["body"] == "buyer internal note" for c in buyer_view.json())


async def test_seller_cannot_post_to_buyers_private_channel(
    client: AsyncClient, buyer: dict, seller: dict, db
):
    deal = await _create_deal(client, buyer, seller, db)
    sel_headers = _auth_headers(seller)

    resp = await client.post(
        f"/deals/{deal['id']}/comments",
        json={"body": "sneaky", "audience": "BUYER_ONLY"},
        headers=sel_headers,
    )
    assert resp.status_code == 403


async def test_superuser_sees_both_private_channels(
    client: AsyncClient, buyer: dict, seller: dict, db
):
    from sqlalchemy import select
    from app.auth.models import User

    deal = await _create_deal(client, buyer, seller, db)
    buy_headers, sel_headers = _auth_headers(buyer), _auth_headers(seller)

    await client.post(
        f"/deals/{deal['id']}/comments",
        json={"body": "buyer secret", "audience": "BUYER_ONLY"}, headers=buy_headers,
    )
    await client.post(
        f"/deals/{deal['id']}/comments",
        json={"body": "seller secret", "audience": "SELLER_ONLY"}, headers=sel_headers,
    )

    result = await db.execute(select(User))
    for u in result.scalars():
        u.is_superuser = True
    await db.commit()

    staff_view = await client.get(f"/deals/{deal['id']}/comments", headers=buy_headers)
    bodies = {c["body"] for c in staff_view.json()}
    assert "buyer secret" in bodies
    assert "seller secret" in bodies


# ── Attachments ───────────────────────────────────────────────────────────────


async def test_private_attachment_hidden_from_other_club(
    client: AsyncClient, buyer: dict, seller: dict, db
):
    deal = await _create_deal(client, buyer, seller, db)
    buy_headers, sel_headers = _auth_headers(buyer), _auth_headers(seller)

    upload_resp = await client.post(
        f"/deals/{deal['id']}/attachments",
        files={"file": ("contract_draft.pdf", b"%PDF-1.4 seller only", "application/pdf")},
        data={"audience": "SELLER_ONLY"},
        headers=sel_headers,
    )
    assert upload_resp.status_code == 201, upload_resp.text
    attachment_id = upload_resp.json()["id"]

    buyer_list = await client.get(f"/deals/{deal['id']}/attachments", headers=buy_headers)
    assert not any(a["id"] == attachment_id for a in buyer_list.json())

    seller_list = await client.get(f"/deals/{deal['id']}/attachments", headers=sel_headers)
    assert any(a["id"] == attachment_id for a in seller_list.json())

    download_resp = await client.get(
        f"/deals/{deal['id']}/attachments/{attachment_id}/download", headers=buy_headers,
    )
    assert download_resp.status_code == 404

    own_download = await client.get(
        f"/deals/{deal['id']}/attachments/{attachment_id}/download", headers=sel_headers,
    )
    assert own_download.status_code == 200


async def test_buyer_cannot_upload_to_sellers_private_channel(
    client: AsyncClient, buyer: dict, seller: dict, db
):
    deal = await _create_deal(client, buyer, seller, db)
    buy_headers = _auth_headers(buyer)

    resp = await client.post(
        f"/deals/{deal['id']}/attachments",
        files={"file": ("t.pdf", b"%PDF-1.4", "application/pdf")},
        data={"audience": "SELLER_ONLY"},
        headers=buy_headers,
    )
    assert resp.status_code == 403
