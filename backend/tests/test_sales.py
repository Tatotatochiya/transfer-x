"""M3 — Sales + Bidding tests."""

from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import AsyncClient

from tests.conftest import _auth_headers, _register


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def seller(client: AsyncClient) -> dict:
    return await _register(client, "seller@test.com", club_name="Seller FC")


@pytest_asyncio.fixture
async def buyer(client: AsyncClient) -> dict:
    return await _register(client, "buyer@test.com", club_name="Buyer FC")


@pytest_asyncio.fixture
async def buyer2(client: AsyncClient) -> dict:
    return await _register(client, "buyer2@test.com", club_name="Buyer2 FC")


async def _create_player(client: AsyncClient, headers: dict, name: str = "Test Player") -> dict:
    resp = await client.post(
        "/players",
        json={"name": name, "position": "FWD"},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _create_sale(
    client: AsyncClient,
    headers: dict,
    player_id: str,
    sale_type: str = "AUCTION",
    asking_price: float = 5_000_000,
    min_increment: float = 500_000,
    deadline: str | None = None,
) -> dict:
    body = {
        "player_id": player_id,
        "sale_type": sale_type,
        "asking_price": asking_price,
        "min_increment": min_increment,
    }
    if deadline:
        body["deadline"] = deadline

    resp = await client.post("/sales", json=body, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _give_budget(client: AsyncClient, admin_headers: dict, club_id: str, budget: float) -> None:
    """Direct DB manipulation isn't available in HTTP tests; use the clubs/me PATCH endpoint.

    For tests we set transfer_budget_total via the club finances — but there's no
    public endpoint for that yet. We'll use the service layer directly via conftest db.
    """
    pass  # Budget tests use the service layer directly; see test_budget_* below.


# ── Sale creation ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_auction_sale(client: AsyncClient, seller: dict):
    headers = _auth_headers(seller)
    player = await _create_player(client, headers)

    resp = await client.post(
        "/sales",
        json={
            "player_id": player["id"],
            "sale_type": "AUCTION",
            "asking_price": 10_000_000,
            "min_increment": 500_000,
        },
        headers=headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["sale_type"] == "AUCTION"
    assert data["status"] == "OPEN"
    assert float(data["asking_price"]) == 10_000_000
    assert data["bid_count"] == 0
    assert data["best_bid"] is None


@pytest.mark.asyncio
async def test_create_fixed_price_sale(client: AsyncClient, seller: dict):
    headers = _auth_headers(seller)
    player = await _create_player(client, headers)

    resp = await client.post(
        "/sales",
        json={
            "player_id": player["id"],
            "sale_type": "FIXED_PRICE",
            "asking_price": 8_000_000,
        },
        headers=headers,
    )
    assert resp.status_code == 201
    assert resp.json()["sale_type"] == "FIXED_PRICE"


@pytest.mark.asyncio
async def test_create_sale_requires_auth(client: AsyncClient, seller: dict):
    headers = _auth_headers(seller)
    player = await _create_player(client, headers)

    resp = await client.post(
        "/sales",
        json={"player_id": player["id"], "sale_type": "AUCTION"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_sales_public(client: AsyncClient, seller: dict):
    headers = _auth_headers(seller)
    player = await _create_player(client, headers)
    await _create_sale(client, headers, player["id"])

    resp = await client.get("/sales")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert len(data["items"]) >= 1


@pytest.mark.asyncio
async def test_get_sale_by_id(client: AsyncClient, seller: dict):
    headers = _auth_headers(seller)
    player = await _create_player(client, headers)
    sale = await _create_sale(client, headers, player["id"])

    resp = await client.get(f"/sales/{sale['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == sale["id"]


@pytest.mark.asyncio
async def test_get_sale_not_found(client: AsyncClient):
    resp = await client.get("/sales/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


# ── Withdraw ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_withdraw_own_sale(client: AsyncClient, seller: dict):
    headers = _auth_headers(seller)
    player = await _create_player(client, headers)
    sale = await _create_sale(client, headers, player["id"])

    resp = await client.post(f"/sales/{sale['id']}/withdraw", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "WITHDRAWN"


@pytest.mark.asyncio
async def test_withdraw_already_withdrawn(client: AsyncClient, seller: dict):
    headers = _auth_headers(seller)
    player = await _create_player(client, headers)
    sale = await _create_sale(client, headers, player["id"])

    await client.post(f"/sales/{sale['id']}/withdraw", headers=headers)
    resp = await client.post(f"/sales/{sale['id']}/withdraw", headers=headers)
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_withdraw_other_clubs_sale(client: AsyncClient, seller: dict, buyer: dict):
    sel_headers = _auth_headers(seller)
    player = await _create_player(client, sel_headers)
    sale = await _create_sale(client, sel_headers, player["id"])

    resp = await client.post(f"/sales/{sale['id']}/withdraw", headers=_auth_headers(buyer))
    assert resp.status_code == 403


# ── Bidding ───────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_place_bid_requires_auth(client: AsyncClient, seller: dict):
    headers = _auth_headers(seller)
    player = await _create_player(client, headers)
    sale = await _create_sale(client, headers, player["id"])

    resp = await client.post(f"/sales/{sale['id']}/bids", json={"amount": 6_000_000})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_seller_cannot_bid_own_sale(client: AsyncClient, seller: dict, db):
    """Seller bidding on own sale should be rejected."""
    from decimal import Decimal

    from app.clubs.models import ClubFinance
    from sqlalchemy import select

    sel_headers = _auth_headers(seller)
    player = await _create_player(client, sel_headers)
    sale = await _create_sale(client, sel_headers, player["id"])

    # Give seller budget so the check doesn't fail on budget first
    result = await db.execute(select(ClubFinance))
    finances = list(result.scalars())
    for f in finances:
        f.transfer_budget_total = Decimal("100000000")
    await db.commit()

    resp = await client.post(
        f"/sales/{sale['id']}/bids",
        json={"amount": 6_000_000},
        headers=sel_headers,
    )
    assert resp.status_code == 400
    assert "own" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_bid_below_minimum_rejected(client: AsyncClient, seller: dict, buyer: dict, db):
    from decimal import Decimal

    from app.clubs.models import ClubFinance
    from sqlalchemy import select

    sel_headers = _auth_headers(seller)
    player = await _create_player(client, sel_headers)
    sale = await _create_sale(client, sel_headers, player["id"], asking_price=5_000_000, min_increment=500_000)

    result = await db.execute(select(ClubFinance))
    for f in result.scalars():
        f.transfer_budget_total = Decimal("100000000")
    await db.commit()

    resp = await client.post(
        f"/sales/{sale['id']}/bids",
        json={"amount": 1_000},  # way below asking_price
        headers=_auth_headers(buyer),
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_bid_on_non_auction_sale_rejected(client: AsyncClient, seller: dict, buyer: dict, db):
    from decimal import Decimal

    from app.clubs.models import ClubFinance
    from sqlalchemy import select

    sel_headers = _auth_headers(seller)
    player = await _create_player(client, sel_headers)
    sale = await _create_sale(client, sel_headers, player["id"], sale_type="FIXED_PRICE")

    result = await db.execute(select(ClubFinance))
    for f in result.scalars():
        f.transfer_budget_total = Decimal("100000000")
    await db.commit()

    resp = await client.post(
        f"/sales/{sale['id']}/bids",
        json={"amount": 8_000_000},
        headers=_auth_headers(buyer),
    )
    assert resp.status_code == 400
    assert "AUCTION" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_place_valid_bid(client: AsyncClient, seller: dict, buyer: dict, db):
    from decimal import Decimal

    from app.clubs.models import ClubFinance
    from sqlalchemy import select

    sel_headers = _auth_headers(seller)
    player = await _create_player(client, sel_headers)
    sale = await _create_sale(client, sel_headers, player["id"], asking_price=5_000_000)

    result = await db.execute(select(ClubFinance))
    for f in result.scalars():
        f.transfer_budget_total = Decimal("100000000")
    await db.commit()

    resp = await client.post(
        f"/sales/{sale['id']}/bids",
        json={"amount": 5_000_000},
        headers=_auth_headers(buyer),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert float(data["amount"]) == 5_000_000
    assert data["status"] == "ACTIVE"


@pytest.mark.asyncio
async def test_upgrade_bid(client: AsyncClient, seller: dict, buyer: dict, db):
    """Same buyer can raise their bid."""
    from decimal import Decimal

    from app.clubs.models import ClubFinance
    from sqlalchemy import select

    sel_headers = _auth_headers(seller)
    player = await _create_player(client, sel_headers)
    sale = await _create_sale(client, sel_headers, player["id"], asking_price=5_000_000, min_increment=500_000)

    result = await db.execute(select(ClubFinance))
    for f in result.scalars():
        f.transfer_budget_total = Decimal("100000000")
    await db.commit()

    buy_headers = _auth_headers(buyer)
    resp1 = await client.post(
        f"/sales/{sale['id']}/bids", json={"amount": 5_000_000}, headers=buy_headers
    )
    assert resp1.status_code == 201

    resp2 = await client.post(
        f"/sales/{sale['id']}/bids", json={"amount": 6_000_000}, headers=buy_headers
    )
    assert resp2.status_code == 201
    assert float(resp2.json()["amount"]) == 6_000_000

    # Should still only have one active bid from this buyer
    resp3 = await client.get(
        f"/sales/{sale['id']}/bids", headers=buy_headers
    )
    assert resp3.status_code == 200
    assert len(resp3.json()) == 1


@pytest.mark.asyncio
async def test_sale_shows_bid_count_and_best(client: AsyncClient, seller: dict, buyer: dict, db):
    from decimal import Decimal

    from app.clubs.models import ClubFinance
    from sqlalchemy import select

    sel_headers = _auth_headers(seller)
    player = await _create_player(client, sel_headers)
    sale = await _create_sale(client, sel_headers, player["id"], asking_price=5_000_000)

    result = await db.execute(select(ClubFinance))
    for f in result.scalars():
        f.transfer_budget_total = Decimal("100000000")
    await db.commit()

    await client.post(
        f"/sales/{sale['id']}/bids", json={"amount": 5_000_000}, headers=_auth_headers(buyer)
    )

    # TRA-139: bid_count/best_bid are only visible to the seller
    resp = await client.get(f"/sales/{sale['id']}", headers=sel_headers)
    data = resp.json()
    assert data["bid_count"] == 1
    assert float(data["best_bid"]) == 5_000_000
    assert float(data["minimum_next_bid"]) == 5_500_000


# ── Accept bid ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_accept_bid_creates_deal(client: AsyncClient, seller: dict, buyer: dict, db):
    from decimal import Decimal

    from app.clubs.models import ClubFinance
    from sqlalchemy import select

    sel_headers = _auth_headers(seller)
    buy_headers = _auth_headers(buyer)
    player = await _create_player(client, sel_headers)
    sale = await _create_sale(client, sel_headers, player["id"], asking_price=5_000_000)

    result = await db.execute(select(ClubFinance))
    for f in result.scalars():
        f.transfer_budget_total = Decimal("100000000")
    await db.commit()

    bid_resp = await client.post(
        f"/sales/{sale['id']}/bids", json={"amount": 5_000_000}, headers=buy_headers
    )
    bid_id = bid_resp.json()["id"]

    resp = await client.post(
        f"/sales/{sale['id']}/bids/{bid_id}/accept", headers=sel_headers
    )
    assert resp.status_code == 200
    deal = resp.json()
    assert deal["status"] == "IN_PROGRESS"
    assert deal["stage"] == "AGREEMENT"
    assert float(deal["agreed_fee"]) == 5_000_000.0

    # Sale should now be CLOSED
    sale_resp = await client.get(f"/sales/{sale['id']}")
    assert sale_resp.json()["status"] == "CLOSED"


@pytest.mark.asyncio
async def test_accept_bid_notifies_losing_bidders(
    client: AsyncClient, seller: dict, buyer: dict, buyer2: dict, db
):
    """Item 1: losing bidders get their budget released but were never told why."""
    from decimal import Decimal

    from sqlalchemy import select

    from app.auth.models import User
    from app.clubs.models import ClubFinance
    from app.notifications.models import Notification, NotificationType

    sel_headers = _auth_headers(seller)
    buy_headers = _auth_headers(buyer)
    buy2_headers = _auth_headers(buyer2)
    player = await _create_player(client, sel_headers)
    sale = await _create_sale(client, sel_headers, player["id"], asking_price=5_000_000)

    result = await db.execute(select(ClubFinance))
    for f in result.scalars():
        f.transfer_budget_total = Decimal("100000000")
    await db.commit()

    losing_bid = await client.post(
        f"/sales/{sale['id']}/bids", json={"amount": 5_000_000}, headers=buy2_headers
    )
    assert losing_bid.status_code == 201
    winning_bid = await client.post(
        f"/sales/{sale['id']}/bids", json={"amount": 6_000_000}, headers=buy_headers
    )
    assert winning_bid.status_code == 201
    bid_id = winning_bid.json()["id"]

    resp = await client.post(f"/sales/{sale['id']}/bids/{bid_id}/accept", headers=sel_headers)
    assert resp.status_code == 200

    await db.rollback()
    loser_user_id = (await db.execute(select(User).where(User.email == "buyer2@test.com"))).scalar_one().id
    notif_result = await db.execute(
        select(Notification).where(
            Notification.recipient_user_id == loser_user_id,
            Notification.type == NotificationType.OUTBID,
        )
    )
    assert notif_result.scalars().first() is not None


@pytest.mark.asyncio
async def test_buyer_cannot_accept_bid(client: AsyncClient, seller: dict, buyer: dict, db):
    from decimal import Decimal

    from app.clubs.models import ClubFinance
    from sqlalchemy import select

    sel_headers = _auth_headers(seller)
    buy_headers = _auth_headers(buyer)
    player = await _create_player(client, sel_headers)
    sale = await _create_sale(client, sel_headers, player["id"], asking_price=5_000_000)

    result = await db.execute(select(ClubFinance))
    for f in result.scalars():
        f.transfer_budget_total = Decimal("100000000")
    await db.commit()

    bid_resp = await client.post(
        f"/sales/{sale['id']}/bids", json={"amount": 5_000_000}, headers=buy_headers
    )
    bid_id = bid_resp.json()["id"]

    resp = await client.post(
        f"/sales/{sale['id']}/bids/{bid_id}/accept", headers=buy_headers
    )
    assert resp.status_code == 400


# ── Budget reservation checks ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_bid_fails_with_no_budget(client: AsyncClient, seller: dict, buyer: dict, db):
    """Buyer with zero budget cannot place a bid."""
    sel_headers = _auth_headers(seller)
    player = await _create_player(client, sel_headers)
    sale = await _create_sale(client, sel_headers, player["id"], asking_price=5_000_000)

    resp = await client.post(
        f"/sales/{sale['id']}/bids",
        json={"amount": 5_000_000},
        headers=_auth_headers(buyer),
    )
    assert resp.status_code == 400
    assert "budget" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_withdraw_sale_releases_bid_reservations(
    client: AsyncClient, seller: dict, buyer: dict, db
):
    from decimal import Decimal

    from app.clubs.models import ClubFinance
    from sqlalchemy import select

    sel_headers = _auth_headers(seller)
    buy_headers = _auth_headers(buyer)
    player = await _create_player(client, sel_headers)
    sale = await _create_sale(client, sel_headers, player["id"], asking_price=5_000_000)

    result = await db.execute(select(ClubFinance))
    finances = list(result.scalars())
    for f in finances:
        f.transfer_budget_total = Decimal("10000000")
    await db.commit()

    await client.post(
        f"/sales/{sale['id']}/bids", json={"amount": 5_000_000}, headers=buy_headers
    )

    # Before withdraw: budget should be partially reserved
    await db.refresh(finances[0])
    await db.refresh(finances[1])

    await client.post(f"/sales/{sale['id']}/withdraw", headers=sel_headers)

    # After withdraw: all reservations released
    await db.refresh(finances[0])
    await db.refresh(finances[1])
    for f in finances:
        assert f.transfer_reserved == Decimal("0")


@pytest.mark.asyncio
async def test_withdraw_sale_notifies_bidders(client: AsyncClient, seller: dict, buyer: dict, db):
    """Item 1: withdrawing a sale must tell active bidders, not just release funds."""
    from decimal import Decimal

    from app.auth.models import User
    from app.clubs.models import ClubFinance
    from app.notifications.models import Notification, NotificationType
    from sqlalchemy import select

    sel_headers = _auth_headers(seller)
    buy_headers = _auth_headers(buyer)
    player = await _create_player(client, sel_headers)
    sale = await _create_sale(client, sel_headers, player["id"], asking_price=5_000_000)

    result = await db.execute(select(ClubFinance))
    for f in result.scalars():
        f.transfer_budget_total = Decimal("10000000")
    await db.commit()

    await client.post(f"/sales/{sale['id']}/bids", json={"amount": 5_000_000}, headers=buy_headers)
    await client.post(f"/sales/{sale['id']}/withdraw", headers=sel_headers)

    await db.rollback()
    buyer_user_id = (await db.execute(select(User).where(User.email == "buyer@test.com"))).scalar_one().id
    notif_result = await db.execute(
        select(Notification).where(
            Notification.recipient_user_id == buyer_user_id,
            Notification.type == NotificationType.OUTBID,
        )
    )
    assert notif_result.scalars().first() is not None


@pytest.mark.asyncio
async def test_withdraw_sale_rejects_linked_offers(client: AsyncClient, seller: dict, buyer: dict, db):
    """Item 1: direct offers against an OPEN_TO_OFFERS listing must not survive
    the listing's withdrawal and remain acceptable."""
    from decimal import Decimal

    from app.clubs.models import ClubFinance
    from sqlalchemy import select

    sel_headers = _auth_headers(seller)
    buy_headers = _auth_headers(buyer)
    player = await _create_player(client, sel_headers)
    sale = await _create_sale(client, sel_headers, player["id"], sale_type="OPEN_TO_OFFERS")

    result = await db.execute(select(ClubFinance))
    for f in result.scalars():
        f.transfer_budget_total = Decimal("10000000")
    await db.commit()

    offer_resp = await client.post(
        "/offers",
        json={"player_id": player["id"], "sale_id": sale["id"], "fee_amount": 5_000_000},
        headers=buy_headers,
    )
    assert offer_resp.status_code == 201, offer_resp.text
    offer_id = offer_resp.json()["id"]

    await client.post(f"/sales/{sale['id']}/withdraw", headers=sel_headers)

    offer_after = await client.get(f"/offers/{offer_id}", headers=buy_headers)
    assert offer_after.json()["status"] == "REJECTED"

    finance_after = await client.get("/clubs/me", headers=buy_headers)
    assert Decimal(finance_after.json()["finance"]["transfer_reserved"]) == Decimal("0")


@pytest.mark.asyncio
async def test_close_expired_sales_notifies_bidders(client: AsyncClient, seller: dict, buyer: dict, db):
    """Item 1: an auction lapsing with no accepted bid must tell bidders, not
    just silently release their reservation."""
    import uuid
    from datetime import datetime, timedelta, timezone
    from decimal import Decimal

    from app.auth.models import User
    from app.clubs.models import ClubFinance
    from app.notifications.models import Notification, NotificationType
    from app.sales.models import Sale
    from app.sales.service import close_expired_sales
    from sqlalchemy import select

    sel_headers = _auth_headers(seller)
    buy_headers = _auth_headers(buyer)
    player = await _create_player(client, sel_headers)
    sale = await _create_sale(client, sel_headers, player["id"])

    result = await db.execute(select(ClubFinance))
    for f in result.scalars():
        f.transfer_budget_total = Decimal("10000000")
    await db.commit()

    # No deadline until after the bid lands — SQLite round-trips DateTime as
    # naive, so setting it before place_bid's own deadline check would trip
    # a naive/aware comparison TypeError unrelated to what this test covers.
    await client.post(f"/sales/{sale['id']}/bids", json={"amount": 5_000_000}, headers=buy_headers)

    sale_row = await db.get(Sale, uuid.UUID(sale["id"]))
    sale_row.deadline = datetime.now(timezone.utc) - timedelta(minutes=1)
    await db.commit()

    count = await close_expired_sales(db)
    await db.commit()
    assert count == 1

    await db.rollback()
    buyer_user_id = (await db.execute(select(User).where(User.email == "buyer@test.com"))).scalar_one().id
    notif_result = await db.execute(
        select(Notification).where(
            Notification.recipient_user_id == buyer_user_id,
            Notification.type == NotificationType.OUTBID,
        )
    )
    assert notif_result.scalars().first() is not None


# ── TRA-139: reserve price / bid competition scoping ──────────────────────────


@pytest.mark.asyncio
async def test_reserve_price_hidden_from_non_seller(client: AsyncClient, seller: dict, buyer: dict):
    sel_headers = _auth_headers(seller)
    player = await _create_player(client, sel_headers)
    resp = await client.post(
        "/sales",
        json={
            "player_id": player["id"],
            "sale_type": "AUCTION",
            "asking_price": 5_000_000,
            "reserve_price": 7_000_000,
            "min_increment": 500_000,
        },
        headers=sel_headers,
    )
    assert resp.status_code == 201
    sale_id = resp.json()["id"]
    assert float(resp.json()["reserve_price"]) == 7_000_000  # seller sees it on create

    anon_data = (await client.get(f"/sales/{sale_id}")).json()
    assert anon_data["reserve_price"] is None

    buyer_data = (await client.get(f"/sales/{sale_id}", headers=_auth_headers(buyer))).json()
    assert buyer_data["reserve_price"] is None

    seller_data = (await client.get(f"/sales/{sale_id}", headers=sel_headers)).json()
    assert float(seller_data["reserve_price"]) == 7_000_000


@pytest.mark.asyncio
async def test_bid_count_and_best_bid_hidden_from_non_seller(
    client: AsyncClient, seller: dict, buyer: dict, buyer2: dict, db
):
    from decimal import Decimal

    from app.clubs.models import ClubFinance
    from sqlalchemy import select

    sel_headers = _auth_headers(seller)
    player = await _create_player(client, sel_headers)
    sale = await _create_sale(client, sel_headers, player["id"], asking_price=5_000_000)

    result = await db.execute(select(ClubFinance))
    for f in result.scalars():
        f.transfer_budget_total = Decimal("100000000")
    await db.commit()

    await client.post(
        f"/sales/{sale['id']}/bids", json={"amount": 5_000_000}, headers=_auth_headers(buyer)
    )

    # A rival club sees neither bid_count nor best_bid...
    rival_data = (await client.get(f"/sales/{sale['id']}", headers=_auth_headers(buyer2))).json()
    assert rival_data["bid_count"] is None
    assert rival_data["best_bid"] is None
    # ...but still gets the minimum valid next bid, since they need it to bid at all
    assert float(rival_data["minimum_next_bid"]) == 5_500_000

    anon_data = (await client.get(f"/sales/{sale['id']}")).json()
    assert anon_data["bid_count"] is None
    assert anon_data["best_bid"] is None

    seller_data = (await client.get(f"/sales/{sale['id']}", headers=sel_headers)).json()
    assert seller_data["bid_count"] == 1
    assert float(seller_data["best_bid"]) == 5_000_000


# ── TRA-138: seller must own the player being listed ──────────────────────────


@pytest.mark.asyncio
async def test_cannot_list_player_not_owned_by_club(client: AsyncClient, seller: dict, buyer: dict):
    sel_headers = _auth_headers(seller)
    player = await _create_player(client, sel_headers)  # registered to `seller`

    resp = await client.post(
        "/sales",
        json={"player_id": player["id"], "sale_type": "AUCTION", "asking_price": 5_000_000},
        headers=_auth_headers(buyer),  # buyer tries to list seller's player
    )
    assert resp.status_code == 400
    assert "not registered" in resp.json()["detail"].lower()


# ── TRA-91: fair-value signal embed on sale detail ─────────────────────────────


async def _seed_valuation(client: AsyncClient, db, player_id: str) -> None:
    """Insert Example-A stats and compute a valuation as staff."""
    import uuid as uuid_mod
    from sqlalchemy import select
    from app.auth.models import User
    from app.players.models import Player
    from app.stats.models import PlayerStats

    # test_sales' _create_player sets no age; Example A expects a 25-year-old
    result = await db.execute(select(Player).where(Player.id == uuid_mod.UUID(player_id)))
    result.scalar_one().age = 25

    db.add(PlayerStats(
        player_id=uuid_mod.UUID(player_id), vendor="api_sports_v3",
        league_id="39", season="2025", minutes=2700, appearances=30,
        goals=24, assists=9, shots_on_target=54, key_passes=45,
        dribbles_success=60, avg_rating=7.6,
    ))
    await db.commit()

    email = f"saleval-admin-{uuid_mod.uuid4().hex[:6]}@test.com"
    admin_tokens = await _register(client, email)
    result = await db.execute(select(User).where(User.email == email))
    result.scalar_one().is_superuser = True
    await db.commit()
    resp = await client.post(
        f"/valuation/players/{player_id}/recompute", headers=_auth_headers(admin_tokens)
    )
    assert resp.status_code == 200, resp.text


@pytest.mark.asyncio
async def test_fixed_price_sale_embeds_signal_with_divergence(
    client: AsyncClient, seller: dict, buyer: dict, db
):
    sel_headers = _auth_headers(seller)
    player = await _create_player(client, sel_headers)
    await _seed_valuation(client, db, player["id"])
    sale = await _create_sale(
        client, sel_headers, player["id"], sale_type="FIXED_PRICE", asking_price=80_000_000
    )

    data = (await client.get(f"/sales/{sale['id']}", headers=_auth_headers(buyer))).json()
    signal = data["fair_value_signal"]
    assert signal is not None
    assert abs(float(signal["fair_value"]) - 66_500_000) <= 100_000
    assert signal["divergence"] is not None
    assert float(signal["divergence"]["reference_price"]) == 80_000_000
    assert signal["divergence"]["band"] == "ABOVE"


@pytest.mark.asyncio
async def test_open_to_offers_sale_embeds_signal_with_divergence(
    client: AsyncClient, seller: dict, buyer: dict, db
):
    """An OPEN_TO_OFFERS asking price is seller-stated and already public on the
    listing, so it is a valid reference. Only AUCTION is excluded (D7), whose
    seller-side numbers — reserve and bids — are the hidden ones."""
    sel_headers = _auth_headers(seller)
    player = await _create_player(client, sel_headers)
    await _seed_valuation(client, db, player["id"])
    sale = await _create_sale(
        client, sel_headers, player["id"],
        sale_type="OPEN_TO_OFFERS", asking_price=80_000_000,
    )

    data = (await client.get(f"/sales/{sale['id']}", headers=_auth_headers(buyer))).json()
    signal = data["fair_value_signal"]
    assert signal is not None
    assert signal["divergence"] is not None
    assert float(signal["divergence"]["reference_price"]) == 80_000_000
    assert signal["divergence"]["band"] == "ABOVE"


@pytest.mark.asyncio
async def test_auction_sale_embeds_signal_without_divergence(
    client: AsyncClient, seller: dict, buyer: dict, db
):
    """D7: an auction's signal must never carry a divergence — a divergence
    against the (hidden) reserve would leak it."""
    sel_headers = _auth_headers(seller)
    player = await _create_player(client, sel_headers)
    await _seed_valuation(client, db, player["id"])

    resp = await client.post(
        "/sales",
        json={
            "player_id": player["id"], "sale_type": "AUCTION",
            "asking_price": 5_000_000, "reserve_price": 7_000_000,
        },
        headers=sel_headers,
    )
    assert resp.status_code == 201, resp.text
    sale_id = resp.json()["id"]

    data = (await client.get(f"/sales/{sale_id}", headers=_auth_headers(buyer))).json()
    signal = data["fair_value_signal"]
    assert signal is not None
    assert signal["divergence"] is None
    # nothing derived from reserve_price appears anywhere in the signal
    assert data["reserve_price"] is None  # TRA-139 scoping still holds
    assert "7000000" not in str(signal)


async def _set_market_value(db, player_id: str, value: int) -> None:
    import uuid as uuid_mod

    from sqlalchemy import select

    from app.players.models import Player

    row = (
        await db.execute(select(Player).where(Player.id == uuid_mod.UUID(player_id)))
    ).scalar_one()
    row.market_value = Decimal(str(value))
    await db.commit()


@pytest.mark.asyncio
async def test_fixed_price_sale_falls_back_to_market_value_when_asking_unset(
    client: AsyncClient, seller: dict, buyer: dict, db
):
    """`asking_price` is optional at creation for every sale type — CreateSalePage
    never requires it outside AUCTION's deadline — so a FIXED_PRICE listing with
    none set is a reachable state, not a hypothetical. Same fallback order as
    the batch (`get_reference_prices`): without this, a player's row in the
    market list could show a divergence via market_value while this same
    player's own sale page showed none at all."""
    sel_headers = _auth_headers(seller)
    player = await _create_player(client, sel_headers)
    await _seed_valuation(client, db, player["id"])
    await _set_market_value(db, player["id"], 80_000_000)
    sale = await _create_sale(
        client, sel_headers, player["id"], sale_type="FIXED_PRICE", asking_price=None,
    )

    data = (await client.get(f"/sales/{sale['id']}", headers=_auth_headers(buyer))).json()
    signal = data["fair_value_signal"]
    assert signal is not None
    assert signal["divergence"] is not None
    assert float(signal["divergence"]["reference_price"]) == 80_000_000
    assert signal["divergence"]["band"] == "ABOVE"


@pytest.mark.asyncio
async def test_open_to_offers_sale_falls_back_to_market_value_when_asking_unset(
    client: AsyncClient, seller: dict, buyer: dict, db
):
    """Same fallback as FIXED_PRICE above — the rule is "any non-auction
    listing", not one sale type, matching the batch and D7's own scope."""
    sel_headers = _auth_headers(seller)
    player = await _create_player(client, sel_headers)
    await _seed_valuation(client, db, player["id"])
    await _set_market_value(db, player["id"], 40_000_000)
    sale = await _create_sale(
        client, sel_headers, player["id"], sale_type="OPEN_TO_OFFERS", asking_price=None,
    )

    data = (await client.get(f"/sales/{sale['id']}", headers=_auth_headers(buyer))).json()
    signal = data["fair_value_signal"]
    assert signal is not None
    assert signal["divergence"] is not None
    assert float(signal["divergence"]["reference_price"]) == 40_000_000


@pytest.mark.asyncio
async def test_auction_sale_never_falls_back_to_market_value(
    client: AsyncClient, seller: dict, buyer: dict, db
):
    """D7 is a hard exclusion, not just "no asking_price set" — an auction must
    stay divergence-free even when the player has a market_value that would
    otherwise satisfy the same fallback FIXED_PRICE/OPEN_TO_OFFERS just got."""
    sel_headers = _auth_headers(seller)
    player = await _create_player(client, sel_headers)
    await _seed_valuation(client, db, player["id"])
    await _set_market_value(db, player["id"], 80_000_000)

    resp = await client.post(
        "/sales",
        json={"player_id": player["id"], "sale_type": "AUCTION", "asking_price": 5_000_000},
        headers=sel_headers,
    )
    assert resp.status_code == 201, resp.text
    sale_id = resp.json()["id"]

    data = (await client.get(f"/sales/{sale_id}", headers=_auth_headers(buyer))).json()
    signal = data["fair_value_signal"]
    assert signal is not None
    assert signal["divergence"] is None


@pytest.mark.asyncio
async def test_sale_embed_null_for_player_account_and_anonymous(
    client: AsyncClient, seller: dict, db
):
    sel_headers = _auth_headers(seller)
    player = await _create_player(client, sel_headers)
    await _seed_valuation(client, db, player["id"])
    sale = await _create_sale(
        client, sel_headers, player["id"], sale_type="FIXED_PRICE", asking_price=80_000_000
    )

    resp = await client.post("/auth/register", json={
        "email": "saleval-player@test.com", "password": "password123",
        "user_type": "PLAYER", "player_id": player["id"],
    })
    assert resp.status_code == 201, resp.text
    player_headers = _auth_headers(resp.json())

    data = (await client.get(f"/sales/{sale['id']}", headers=player_headers)).json()
    assert data["fair_value_signal"] is None

    anon = (await client.get(f"/sales/{sale['id']}")).json()
    assert anon["fair_value_signal"] is None


@pytest.mark.asyncio
async def test_sale_embed_null_for_ineligible_player(client: AsyncClient, seller: dict, buyer: dict):
    sel_headers = _auth_headers(seller)
    player = await _create_player(client, sel_headers)  # no stats → no valuation
    sale = await _create_sale(
        client, sel_headers, player["id"], sale_type="FIXED_PRICE", asking_price=8_000_000
    )
    data = (await client.get(f"/sales/{sale['id']}", headers=_auth_headers(buyer))).json()
    assert data["fair_value_signal"] is None


# ── B1: whose_move ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_sale_whose_move_neither_with_no_bids(client: AsyncClient, seller: dict):
    headers = _auth_headers(seller)
    player = await _create_player(client, headers)
    sale = await _create_sale(client, headers, player["id"])

    resp = await client.get(f"/sales/{sale['id']}", headers=headers)
    assert resp.json()["whose_move"] == "neither"


@pytest.mark.asyncio
async def test_sale_whose_move_your_when_bid_placed_and_closing_soon(
    client: AsyncClient, seller: dict, buyer: dict, db
):
    from datetime import datetime, timedelta, timezone

    from app.clubs.models import ClubFinance
    from sqlalchemy import select

    sel_headers = _auth_headers(seller)
    buy_headers = _auth_headers(buyer)
    player = await _create_player(client, sel_headers)
    deadline = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
    sale = await _create_sale(client, sel_headers, player["id"], deadline=deadline)

    result = await db.execute(select(ClubFinance))
    for f in result.scalars():
        f.transfer_budget_total = Decimal("100000000")
    await db.commit()

    bid_resp = await client.post(f"/sales/{sale['id']}/bids", json={"amount": 5_500_000}, headers=buy_headers)
    assert bid_resp.status_code == 201, bid_resp.text

    seller_view = await client.get(f"/sales/{sale['id']}", headers=sel_headers)
    assert seller_view.json()["whose_move"] == "your"

    # Non-seller viewers never see this — bid_count/reserve figures are seller/staff-only (TRA-139),
    # so a null bid_count falls through to "neither" the same way the frontend's rule does.
    buyer_view = await client.get(f"/sales/{sale['id']}", headers=buy_headers)
    assert buyer_view.json()["whose_move"] == "neither"
