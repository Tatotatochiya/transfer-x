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
