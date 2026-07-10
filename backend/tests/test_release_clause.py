"""Item 14 — release clause bypasses seller consent."""

from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import AsyncClient

from tests.conftest import _auth_headers, _register

pytestmark = pytest.mark.asyncio


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def seller(client: AsyncClient) -> dict:
    return await _register(client, "clause_seller@test.com", club_name="Clause Seller FC")


@pytest_asyncio.fixture
async def buyer(client: AsyncClient) -> dict:
    return await _register(client, "clause_buyer@test.com", club_name="Clause Buyer FC")


async def _give_budget(db, amount: Decimal = Decimal("100000000")):
    from app.clubs.models import ClubFinance
    from sqlalchemy import select

    result = await db.execute(select(ClubFinance))
    for f in result.scalars():
        f.transfer_budget_total = amount
    await db.commit()


async def _create_player_with_clause(
    client: AsyncClient, sel_headers: dict, release_clause: float = 20_000_000,
) -> dict:
    player_resp = await client.post(
        "/players", json={"name": "Clause Player", "position": "FWD"}, headers=sel_headers,
    )
    player = player_resp.json()
    seller_club_id = (await client.get("/clubs/me", headers=sel_headers)).json()["id"]
    await client.post(
        f"/players/{player['id']}/contracts",
        json={"club_id": seller_club_id, "wage_weekly": "50000", "release_clause": release_clause},
        headers=sel_headers,
    )
    return player


# ── Tests ─────────────────────────────────────────────────────────────────────


async def test_trigger_release_clause_creates_deal_without_seller_consent(
    client: AsyncClient, buyer: dict, seller: dict, db,
):
    await _give_budget(db)
    sel_headers, buy_headers = _auth_headers(seller), _auth_headers(buyer)
    player = await _create_player_with_clause(client, sel_headers, release_clause=20_000_000)

    resp = await client.post(f"/players/{player['id']}/trigger-release-clause", headers=buy_headers)
    assert resp.status_code == 200, resp.text
    deal = resp.json()
    assert deal["status"] == "IN_PROGRESS"
    assert deal["stage"] == "AGREEMENT"
    assert float(deal["agreed_fee"]) == 20_000_000


async def test_trigger_release_clause_commits_buyer_budget(
    client: AsyncClient, buyer: dict, seller: dict, db,
):
    await _give_budget(db)
    sel_headers, buy_headers = _auth_headers(seller), _auth_headers(buyer)
    player = await _create_player_with_clause(client, sel_headers, release_clause=20_000_000)

    before = (await client.get("/clubs/me", headers=buy_headers)).json()["finance"]
    await client.post(f"/players/{player['id']}/trigger-release-clause", headers=buy_headers)
    after = (await client.get("/clubs/me", headers=buy_headers)).json()["finance"]

    assert Decimal(before["transfer_remaining"]) - Decimal(after["transfer_remaining"]) == Decimal("20000000")
    assert Decimal(after["transfer_committed"]) - Decimal(before["transfer_committed"]) == Decimal("20000000")


async def test_cannot_trigger_without_a_release_clause(
    client: AsyncClient, buyer: dict, seller: dict, db,
):
    await _give_budget(db)
    sel_headers, buy_headers = _auth_headers(seller), _auth_headers(buyer)
    player_resp = await client.post(
        "/players", json={"name": "No Clause Player", "position": "MID"}, headers=sel_headers,
    )
    player = player_resp.json()
    seller_club_id = (await client.get("/clubs/me", headers=sel_headers)).json()["id"]
    await client.post(
        f"/players/{player['id']}/contracts",
        json={"club_id": seller_club_id, "wage_weekly": "50000"},
        headers=sel_headers,
    )

    resp = await client.post(f"/players/{player['id']}/trigger-release-clause", headers=buy_headers)
    assert resp.status_code == 400
    assert "release clause" in resp.json()["detail"].lower()


async def test_cannot_trigger_own_players_clause(client: AsyncClient, seller: dict, db):
    await _give_budget(db)
    sel_headers = _auth_headers(seller)
    player = await _create_player_with_clause(client, sel_headers, release_clause=20_000_000)

    resp = await client.post(f"/players/{player['id']}/trigger-release-clause", headers=sel_headers)
    assert resp.status_code == 400
    assert "own player" in resp.json()["detail"].lower()


async def test_insufficient_budget_rejected(client: AsyncClient, buyer: dict, seller: dict, db):
    sel_headers, buy_headers = _auth_headers(seller), _auth_headers(buyer)
    player = await _create_player_with_clause(client, sel_headers, release_clause=20_000_000)
    # No budget given to buyer.

    resp = await client.post(f"/players/{player['id']}/trigger-release-clause", headers=buy_headers)
    assert resp.status_code == 400
    assert "budget" in resp.json()["detail"].lower()


async def test_notifies_seller_and_rejects_rival_offers(
    client: AsyncClient, buyer: dict, seller: dict, db,
):
    from sqlalchemy import select

    from app.auth.models import User
    from app.notifications.models import Notification, NotificationType

    await _give_budget(db)
    sel_headers, buy_headers = _auth_headers(seller), _auth_headers(buyer)
    player = await _create_player_with_clause(client, sel_headers, release_clause=20_000_000)
    seller_club_id = (await client.get("/clubs/me", headers=sel_headers)).json()["id"]

    rival = await _register(client, "clause_rival@test.com", club_name="Clause Rival FC")
    rival_headers = _auth_headers(rival)
    await _give_budget(db)  # bulk-set covers the rival club too, now that it exists
    rival_offer = await client.post(
        "/offers",
        json={"player_id": player["id"], "to_club_id": seller_club_id, "fee_amount": 10_000_000},
        headers=rival_headers,
    )
    assert rival_offer.status_code == 201

    resp = await client.post(f"/players/{player['id']}/trigger-release-clause", headers=buy_headers)
    assert resp.status_code == 200, resp.text

    rival_offer_after = await client.get(f"/offers/{rival_offer.json()['id']}", headers=rival_headers)
    assert rival_offer_after.json()["status"] == "REJECTED"

    await db.rollback()
    seller_user_id = (await db.execute(select(User).where(User.email == "clause_seller@test.com"))).scalar_one().id
    notif = await db.execute(
        select(Notification).where(
            Notification.recipient_user_id == seller_user_id,
            Notification.type == NotificationType.RELEASE_CLAUSE_TRIGGERED,
        )
    )
    assert notif.scalars().first() is not None
