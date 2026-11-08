"""M3 — Sales (listings) tests. Auctions are retired (product ADR 0011)."""

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
    sale_type: str = "OPEN_TO_OFFERS",
    asking_price: float = 5_000_000,
    deadline: str | None = None,
) -> dict:
    body = {
        "player_id": player_id,
        "sale_type": sale_type,
        "asking_price": asking_price,
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
async def test_auctions_are_no_longer_offered(client: AsyncClient, seller: dict):
    """ADR 0011: a club lists a player open to offers and chooses among them."""
    headers = _auth_headers(seller)
    player = await _create_player(client, headers)

    resp = await client.post(
        "/sales",
        json={"player_id": player["id"], "sale_type": "AUCTION", "asking_price": 10_000_000},
        headers=headers,
    )
    assert resp.status_code == 400
    assert "open to offers" in resp.json()["detail"]
    assert (await client.get("/sales", params={"status": "OPEN"})).json()["total"] == 0


@pytest.mark.asyncio
async def test_an_open_to_offers_listing_can_say_when_offers_close(client: AsyncClient, seller: dict):
    from datetime import datetime, timedelta, timezone

    headers = _auth_headers(seller)
    player = await _create_player(client, headers)
    until = (datetime.now(timezone.utc) + timedelta(days=5)).replace(microsecond=0)
    sale = await _create_sale(client, headers, player["id"], deadline=until.isoformat())
    assert sale["sale_type"] == "OPEN_TO_OFFERS"
    assert sale["deadline"][:16] == until.isoformat()[:16]
    assert "bid_count" not in sale and "min_increment" not in sale


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
        json={"player_id": player["id"], "sale_type": "OPEN_TO_OFFERS"},
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


# ── Offers on a withdrawn or lapsed listing ───────────────────────────────────


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
async def test_close_expired_sales_expires_a_listing_past_its_date(client: AsyncClient, seller: dict, db):
    """An open-to-offers listing's date is when the club stops hearing offers."""
    import uuid
    from datetime import datetime, timedelta, timezone

    from app.sales.models import Sale
    from app.sales.service import close_expired_sales

    sel_headers = _auth_headers(seller)
    player = await _create_player(client, sel_headers)
    sale = await _create_sale(client, sel_headers, player["id"])

    sale_row = await db.get(Sale, uuid.UUID(sale["id"]))
    sale_row.deadline = datetime.now(timezone.utc) - timedelta(minutes=1)
    await db.commit()

    assert await close_expired_sales(db) == 1
    await db.commit()
    assert (await client.get(f"/sales/{sale['id']}")).json()["status"] == "EXPIRED"


# ── TRA-139: reserve price scoping ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_reserve_price_hidden_from_non_seller(client: AsyncClient, seller: dict, buyer: dict):
    sel_headers = _auth_headers(seller)
    player = await _create_player(client, sel_headers)
    resp = await client.post(
        "/sales",
        json={
            "player_id": player["id"],
            "sale_type": "OPEN_TO_OFFERS",
            "asking_price": 5_000_000,
            "reserve_price": 7_000_000,
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


# ── TRA-138: seller must own the player being listed ──────────────────────────


@pytest.mark.asyncio
async def test_cannot_list_player_not_owned_by_club(client: AsyncClient, seller: dict, buyer: dict):
    sel_headers = _auth_headers(seller)
    player = await _create_player(client, sel_headers)  # registered to `seller`

    resp = await client.post(
        "/sales",
        json={"player_id": player["id"], "sale_type": "OPEN_TO_OFFERS", "asking_price": 5_000_000},
        headers=_auth_headers(buyer),  # buyer tries to list seller's player
    )
    assert resp.status_code == 400
    assert "not registered" in resp.json()["detail"].lower()


# ── TRA-91: fair-value signal embed on sale detail ─────────────────────────────


async def _seed_valuation(client: AsyncClient, db, player_id: str) -> None:
    """Insert Example-A stats and compute a valuation as staff (market-v2: £154.4m)."""
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
        client, sel_headers, player["id"], sale_type="FIXED_PRICE", asking_price=185_000_000
    )

    data = (await client.get(f"/sales/{sale['id']}", headers=_auth_headers(buyer))).json()
    signal = data["fair_value_signal"]
    assert signal is not None
    assert abs(float(signal["fair_value"]) - 154_400_000) <= 100_000
    assert signal["divergence"] is not None
    assert float(signal["divergence"]["reference_price"]) == 185_000_000
    assert signal["divergence"]["band"] == "ABOVE"


@pytest.mark.asyncio
async def test_open_to_offers_sale_embeds_signal_with_divergence(
    client: AsyncClient, seller: dict, buyer: dict, db
):
    """An OPEN_TO_OFFERS asking price is seller-stated and already public on the
    listing, so it is a valid reference."""
    sel_headers = _auth_headers(seller)
    player = await _create_player(client, sel_headers)
    await _seed_valuation(client, db, player["id"])
    sale = await _create_sale(
        client, sel_headers, player["id"],
        sale_type="OPEN_TO_OFFERS", asking_price=185_000_000,
    )

    data = (await client.get(f"/sales/{sale['id']}", headers=_auth_headers(buyer))).json()
    signal = data["fair_value_signal"]
    assert signal is not None
    assert signal["divergence"] is not None
    assert float(signal["divergence"]["reference_price"]) == 185_000_000
    assert signal["divergence"]["band"] == "ABOVE"


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
    never requires it — so a FIXED_PRICE listing with
    none set is a reachable state, not a hypothetical. Same fallback order as
    the batch (`get_reference_prices`): without this, a player's row in the
    market list could show a divergence via market_value while this same
    player's own sale page showed none at all."""
    sel_headers = _auth_headers(seller)
    player = await _create_player(client, sel_headers)
    await _seed_valuation(client, db, player["id"])
    await _set_market_value(db, player["id"], 185_000_000)
    sale = await _create_sale(
        client, sel_headers, player["id"], sale_type="FIXED_PRICE", asking_price=None,
    )

    data = (await client.get(f"/sales/{sale['id']}", headers=_auth_headers(buyer))).json()
    signal = data["fair_value_signal"]
    assert signal is not None
    assert signal["divergence"] is not None
    assert float(signal["divergence"]["reference_price"]) == 185_000_000
    assert signal["divergence"]["band"] == "ABOVE"


@pytest.mark.asyncio
async def test_open_to_offers_sale_falls_back_to_market_value_when_asking_unset(
    client: AsyncClient, seller: dict, buyer: dict, db
):
    """Same fallback as FIXED_PRICE above — the rule is "any
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


# ── One open listing per player ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_a_player_cannot_be_listed_twice(client: AsyncClient, seller: dict):
    """Latent while listing was a full-page form; not once it is two clicks
    from the squad and the player page."""
    headers = _auth_headers(seller)
    player = await _create_player(client, headers)
    await _create_sale(client, headers, player["id"], sale_type="OPEN_TO_OFFERS")

    resp = await client.post(
        "/sales",
        json={"player_id": player["id"], "sale_type": "FIXED_PRICE", "asking_price": 20_000_000},
        headers=headers,
    )
    assert resp.status_code == 409, resp.text
    assert "already listed" in resp.text


@pytest.mark.asyncio
async def test_a_withdrawn_listing_does_not_block_relisting(client: AsyncClient, seller: dict):
    """The guard is on OPEN listings only — withdrawing and relisting at a new
    price is the only way to reprice today, so it must keep working."""
    headers = _auth_headers(seller)
    player = await _create_player(client, headers)
    sale = await _create_sale(client, headers, player["id"], sale_type="OPEN_TO_OFFERS")
    resp = await client.post(f"/sales/{sale['id']}/withdraw", headers=headers)
    assert resp.status_code == 200, resp.text

    again = await client.post(
        "/sales",
        json={"player_id": player["id"], "sale_type": "OPEN_TO_OFFERS"},
        headers=headers,
    )
    assert again.status_code == 201, again.text


@pytest.mark.asyncio
async def test_the_database_itself_refuses_a_second_open_listing(
    client: AsyncClient, seller: dict, db
):
    """The router check cannot see a concurrent request that lands between its
    SELECT and its INSERT. This asserts the index holds on its own, bypassing
    the router entirely."""
    import uuid as uuid_mod

    from sqlalchemy.exc import IntegrityError

    from app.sales.models import Sale, SaleStatus, SaleType

    headers = _auth_headers(seller)
    player = await _create_player(client, headers)
    club_id = (await client.get("/clubs/me", headers=headers)).json()["id"]

    for _ in range(2):
        db.add(Sale(
            player_id=uuid_mod.UUID(player["id"]),
            seller_club_id=uuid_mod.UUID(club_id),
            sale_type=SaleType.OPEN_TO_OFFERS,
            min_increment=Decimal("500000"),
            status=SaleStatus.OPEN,
        ))
    with pytest.raises(IntegrityError):
        await db.commit()
    await db.rollback()
