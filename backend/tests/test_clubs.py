"""Club endpoint tests — M2."""

import uuid
from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import AsyncClient

from tests.conftest import _register, _auth_headers

pytestmark = pytest.mark.asyncio


async def test_register_creates_club(client: AsyncClient):
    tokens = await _register(client, "newclub@test.com", club_name="My FC")
    resp = await client.get("/clubs/me", headers=_auth_headers(tokens))
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "My FC"
    assert data["role"] == "BOTH"
    assert data["finance"] is not None


async def test_register_club_name_defaults_to_email_prefix(client: AsyncClient):
    tokens = await _register(client, "arsenal@test.com", club_name="")
    resp = await client.get("/clubs/me", headers=_auth_headers(tokens))
    assert resp.json()["name"] == "arsenal"


async def test_get_my_club_requires_auth(client: AsyncClient):
    resp = await client.get("/clubs/me")
    assert resp.status_code == 401


async def test_patch_my_club(client: AsyncClient, auth_headers: dict):
    resp = await client.patch(
        "/clubs/me",
        json={"name": "Updated FC", "country": "England", "city": "London"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Updated FC"
    assert data["country"] == "England"
    assert data["city"] == "London"


async def test_patch_my_club_partial(client: AsyncClient, auth_headers: dict):
    """Omitted fields are not overwritten."""
    await client.patch("/clubs/me", json={"country": "Spain"}, headers=auth_headers)
    resp = await client.get("/clubs/me", headers=auth_headers)
    assert resp.json()["country"] == "Spain"
    assert resp.json()["name"] == "Test Club"  # unchanged


async def test_list_clubs(client: AsyncClient):
    await _register(client, "club1@test.com", club_name="Alpha FC")
    await _register(client, "club2@test.com", club_name="Beta United")
    resp = await client.get("/clubs")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 2
    names = [c["name"] for c in data["items"]]
    assert "Alpha FC" in names
    assert "Beta United" in names


async def test_list_clubs_search(client: AsyncClient):
    await _register(client, "a@test.com", club_name="Zeta Athletic")
    await _register(client, "b@test.com", club_name="Omega City")
    resp = await client.get("/clubs?search=Zeta")
    data = resp.json()
    assert all("Zeta" in c["name"] for c in data["items"])


async def test_get_club_by_id(client: AsyncClient, auth_headers: dict):
    # Get our own club's ID first
    my_club = (await client.get("/clubs/me", headers=auth_headers)).json()
    club_id = my_club["id"]

    resp = await client.get(f"/clubs/{club_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == club_id


async def test_get_club_not_found(client: AsyncClient):
    import uuid
    resp = await client.get(f"/clubs/{uuid.uuid4()}")
    assert resp.status_code == 404


async def test_club_finance_initial_values(client: AsyncClient, auth_headers: dict):
    resp = await client.get("/clubs/me", headers=auth_headers)
    finance = resp.json()["finance"]
    assert float(finance["transfer_budget_total"]) == 0.0
    assert float(finance["transfer_remaining"]) == 0.0
    assert float(finance["wage_remaining_weekly"]) == 0.0


# ── B5: commitment breakdown ────────────────────────────────────────────────


@pytest_asyncio.fixture
async def commit_buyer(client: AsyncClient) -> dict:
    return await _register(client, "buyer_commit@test.com", club_name="Commit Buyer FC")


@pytest_asyncio.fixture
async def commit_seller(client: AsyncClient) -> dict:
    return await _register(client, "seller_commit@test.com", club_name="Commit Seller FC")


async def _commit_give_budget(db, amount: Decimal = Decimal("100000000")):
    from sqlalchemy import select

    from app.clubs.models import ClubFinance

    result = await db.execute(select(ClubFinance))
    for f in result.scalars():
        f.transfer_budget_total = amount
    await db.commit()


async def test_commitments_requires_auth(client: AsyncClient):
    resp = await client.get("/clubs/me/commitments")
    assert resp.status_code == 401


async def test_commitments_empty_for_fresh_club(client: AsyncClient, commit_buyer: dict):
    resp = await client.get("/clubs/me/commitments", headers=_auth_headers(commit_buyer))
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert float(data["total_transfer_reserved"]) == 0.0


async def test_commitments_shows_sent_offer_as_reserved(
    client: AsyncClient, commit_buyer: dict, commit_seller: dict, db
):
    await _commit_give_budget(db)
    buy_headers = _auth_headers(commit_buyer)
    sel_headers = _auth_headers(commit_seller)

    player = await client.post(
        "/players", json={"name": "Commit Player", "position": "MID"}, headers=sel_headers
    )
    seller_club_id = (await client.get("/clubs/me", headers=sel_headers)).json()["id"]

    offer = await client.post(
        "/offers",
        json={"player_id": player.json()["id"], "to_club_id": seller_club_id, "fee_amount": 4_000_000},
        headers=buy_headers,
    )
    assert offer.status_code == 201, offer.text

    resp = await client.get("/clubs/me/commitments", headers=buy_headers)
    items = resp.json()["items"]
    match = [i for i in items if i["kind"] == "offer" and i["id"] == offer.json()["id"]]
    assert len(match) == 1
    assert match[0]["status"] == "reserved"
    assert float(match[0]["transfer_amount"]) == 4_000_000

    finance = (await client.get("/clubs/me", headers=buy_headers)).json()["finance"]
    assert float(resp.json()["total_transfer_reserved"]) == float(finance["transfer_reserved"])


async def test_commitments_shows_active_bid_as_reserved(
    client: AsyncClient, commit_buyer: dict, commit_seller: dict, db
):
    await _commit_give_budget(db)
    buy_headers = _auth_headers(commit_buyer)
    sel_headers = _auth_headers(commit_seller)

    player = await client.post(
        "/players", json={"name": "Bid Commit Player", "position": "DEF"}, headers=sel_headers
    )
    sale = await client.post(
        "/sales",
        json={"player_id": player.json()["id"], "sale_type": "AUCTION", "asking_price": 3_000_000},
        headers=sel_headers,
    )
    bid = await client.post(
        f"/sales/{sale.json()['id']}/bids", json={"amount": 3_500_000}, headers=buy_headers
    )
    assert bid.status_code == 201, bid.text

    resp = await client.get("/clubs/me/commitments", headers=buy_headers)
    items = resp.json()["items"]
    match = [i for i in items if i["kind"] == "bid" and i["id"] == bid.json()["id"]]
    assert len(match) == 1
    assert match[0]["status"] == "reserved"
    assert float(match[0]["transfer_amount"]) == 3_500_000

    # The seller's own commitments are untouched by a bid on their listing.
    seller_resp = await client.get("/clubs/me/commitments", headers=sel_headers)
    assert seller_resp.json()["items"] == []


async def test_commitments_shows_in_progress_deal_as_committed(
    client: AsyncClient, commit_buyer: dict, commit_seller: dict, db
):
    await _commit_give_budget(db)
    buy_headers = _auth_headers(commit_buyer)
    sel_headers = _auth_headers(commit_seller)

    player = await client.post(
        "/players", json={"name": "Deal Commit Player", "position": "FWD"}, headers=sel_headers
    )
    seller_club_id = (await client.get("/clubs/me", headers=sel_headers)).json()["id"]
    offer = await client.post(
        "/offers",
        json={"player_id": player.json()["id"], "to_club_id": seller_club_id, "fee_amount": 5_000_000},
        headers=buy_headers,
    )
    deal = await client.post(f"/offers/{offer.json()['id']}/accept", headers=sel_headers)
    assert deal.status_code == 200, deal.text

    # The offer is resolved (ACCEPTED) — it must not double-count as still reserved.
    buyer_items = (await client.get("/clubs/me/commitments", headers=buy_headers)).json()["items"]
    assert [i for i in buyer_items if i["kind"] == "deal" and i["id"] == deal.json()["id"]]
    assert not [i for i in buyer_items if i["kind"] == "offer"]

    # Committed budget is a buyer-side concept — the seller has nothing committed.
    seller_items = (await client.get("/clubs/me/commitments", headers=sel_headers)).json()["items"]
    assert seller_items == []


# ── B6: contract cliff (windowed) ───────────────────────────────────────────


async def _add_contract(db, *, player_id: str, club_id: str, days_out: int, is_active: bool = True):
    import datetime as dt

    from sqlalchemy import select

    from app.players.models import Contract, Player
    from app.players.service import normalize_player_status

    contract = Contract(
        player_id=uuid.UUID(player_id),
        club_id=uuid.UUID(club_id),
        end_date=dt.date.today() + dt.timedelta(days=days_out),
        is_active=is_active,
    )
    db.add(contract)
    await db.flush()

    # current_club_id is derived from the active contract, not set at player
    # creation — must be recomputed explicitly after any contract change
    # (players/service.py's own normalize_player_status docstring: "no signals").
    player = (await db.execute(select(Player).where(Player.id == uuid.UUID(player_id)))).scalar_one()
    await normalize_player_status(db, player)
    await db.commit()


async def _add_valuation(db, *, player_id: str, fair_value: Decimal):
    from app.valuation.constants import ValuationConfidence
    from app.valuation.models import PlayerValuation

    db.add(PlayerValuation(
        player_id=uuid.UUID(player_id),
        fair_value=fair_value,
        fair_value_low=fair_value,
        fair_value_high=fair_value,
        performance_score=Decimal("50"),
        confidence=ValuationConfidence.HIGH,
        model_version="test",
        league_tier=1,
        age_factor=Decimal("1.0"),
    ))
    await db.commit()


async def test_contract_cliff_requires_auth(client: AsyncClient):
    resp = await client.get("/clubs/me/contract-cliff")
    assert resp.status_code == 401


async def test_contract_cliff_empty_for_fresh_club(client: AsyncClient, auth_headers: dict):
    resp = await client.get("/clubs/me/contract-cliff", headers=auth_headers)
    assert resp.status_code == 200
    windows = resp.json()["windows"]
    assert [w["label"] for w in windows] == ["Under 6 months", "6–12 months", "12–24 months"]
    assert all(w["count"] == 0 and float(w["value_at_risk"]) == 0.0 for w in windows)


async def test_contract_cliff_buckets_and_uses_fair_value(client: AsyncClient, auth_headers: dict, db):
    club_id = (await client.get("/clubs/me", headers=auth_headers)).json()["id"]

    soon = await client.post("/players", json={"name": "Cliff Soon", "position": "MID"}, headers=auth_headers)
    mid = await client.post("/players", json={"name": "Cliff Mid", "position": "DEF"}, headers=auth_headers)
    far = await client.post("/players", json={"name": "Cliff Far", "position": "FWD"}, headers=auth_headers)
    beyond = await client.post("/players", json={"name": "Cliff Beyond", "position": "GK"}, headers=auth_headers)
    inactive = await client.post("/players", json={"name": "Cliff Inactive", "position": "MID"}, headers=auth_headers)

    await _add_contract(db, player_id=soon.json()["id"], club_id=club_id, days_out=30)
    await _add_contract(db, player_id=mid.json()["id"], club_id=club_id, days_out=270)
    await _add_contract(db, player_id=far.json()["id"], club_id=club_id, days_out=600)
    await _add_contract(db, player_id=beyond.json()["id"], club_id=club_id, days_out=900)  # outside all windows
    await _add_contract(db, player_id=inactive.json()["id"], club_id=club_id, days_out=30, is_active=False)

    await _add_valuation(db, player_id=soon.json()["id"], fair_value=Decimal("10000000"))

    resp = await client.get("/clubs/me/contract-cliff", headers=auth_headers)
    windows = {w["label"]: w for w in resp.json()["windows"]}

    assert windows["Under 6 months"]["count"] == 1
    assert float(windows["Under 6 months"]["value_at_risk"]) == 10_000_000.0
    assert windows["6–12 months"]["count"] == 1
    assert windows["12–24 months"]["count"] == 1


async def test_contract_cliff_falls_back_to_legacy_market_value(client: AsyncClient, auth_headers: dict, db):
    from sqlalchemy import select

    from app.players.models import Player

    club_id = (await client.get("/clubs/me", headers=auth_headers)).json()["id"]
    player = await client.post("/players", json={"name": "Cliff Legacy", "position": "FWD"}, headers=auth_headers)
    player_id = player.json()["id"]

    # No PlayerValuation row for this player — only the legacy market_value field.
    result = await db.execute(select(Player).where(Player.id == uuid.UUID(player_id)))
    p = result.scalar_one()
    p.market_value = Decimal("2500000")
    await db.commit()

    await _add_contract(db, player_id=player_id, club_id=club_id, days_out=30)

    resp = await client.get("/clubs/me/contract-cliff", headers=auth_headers)
    windows = {w["label"]: w for w in resp.json()["windows"]}
    assert float(windows["Under 6 months"]["value_at_risk"]) == 2_500_000.0

    # /me/expiring-contracts stays a bare array — DashboardPage.tsx already depends on this shape.
    flat = await client.get("/clubs/me/expiring-contracts", headers=auth_headers)
    assert isinstance(flat.json(), list)
