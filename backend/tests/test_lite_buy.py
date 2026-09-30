"""Lite buy flow candidates (docs/feature_spec/lite-mode, BACKEND.md §2a)."""

import uuid
from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import AsyncClient

from app.config import settings
from tests.conftest import _auth_headers, _register
from tests.test_deals import _get_club_id, _give_budget


@pytest.fixture(autouse=True)
def no_model(monkeypatch):
    """Candidates are picked in code; with no model the plain reasons stand."""
    for key in ("anthropic_api_key", "openai_api_key", "deepseek_api_key"):
        monkeypatch.setattr(settings, key, None)


@pytest_asyncio.fixture
async def buyer(client: AsyncClient) -> dict:
    return await _register(client, "buyer_buy@clubs-example.com", club_name="Buying FC")


@pytest_asyncio.fixture
async def seller(client: AsyncClient) -> dict:
    return await _register(client, "seller_buy@clubs-example.com", club_name="Selling FC")


async def _player(client, club, name, position="DEF", age=25) -> dict:
    resp = await client.post("/players", json={"name": name, "position": position, "age": age},
                             headers=_auth_headers(club))
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _value(db, player_id: str, fair: int):
    from app.valuation.models import PlayerValuation, ValuationConfidence

    db.add(PlayerValuation(
        player_id=uuid.UUID(player_id), fair_value=Decimal(fair), fair_value_low=Decimal(fair * 0.8),
        fair_value_high=Decimal(fair * 1.2), performance_score=Decimal("60"),
        confidence=list(ValuationConfidence)[0], model_version="test", league_tier=1, age_factor=Decimal("1"),
    ))
    await db.commit()


async def _candidates(client, club, position, band):
    resp = await client.get(f"/lite/buy/candidates?position={position}&band={band}", headers=_auth_headers(club))
    assert resp.status_code == 200, resp.text
    return resp.json()


@pytest.mark.asyncio
async def test_prices_come_from_the_listing_else_the_model(client: AsyncClient, buyer, seller, db):
    listed = await _player(client, seller, "Listed Larry")
    await client.post("/sales", json={"player_id": listed["id"], "sale_type": "OPEN_TO_OFFERS", "asking_price": 6_000_000},
                      headers=_auth_headers(seller))
    modelled = await _player(client, seller, "Modelled Mo")
    await _value(db, modelled["id"], 8_000_000)
    await _player(client, seller, "Unpriced Ursula")  # no listing, no model: nothing to offer against

    got = await _candidates(client, buyer, "DEF", "5-10")
    by_name = {p["name"]: p for p in got["players"]}
    assert set(by_name) == {"Listed Larry", "Modelled Mo"}
    assert (by_name["Listed Larry"]["price"], by_name["Listed Larry"]["price_basis"]) == (6_000_000, "listed")
    assert (by_name["Modelled Mo"]["price"], by_name["Modelled Mo"]["price_basis"]) == (8_000_000, "model")
    assert by_name["Listed Larry"]["club"] == "Selling FC"
    assert "You have no defenders" in by_name["Listed Larry"]["reason"]


@pytest.mark.asyncio
async def test_only_buyable_players_and_never_your_own(client: AsyncClient, buyer, seller, db):
    from app.players.models import Player, PlayerStatus

    mine = await _player(client, buyer, "My Own Man")
    await _value(db, mine["id"], 3_000_000)
    theirs = await _player(client, seller, "Their Man")
    await _value(db, theirs["id"], 3_000_000)
    external = Player(name="Elsewhere Eddie", position="DEF", status=PlayerStatus.EXTERNAL, team_name="Real Somewhere")
    free = Player(name="Free Fred", position="DEF", status=PlayerStatus.FREE_AGENT, age=26)
    db.add_all([external, free])
    await db.commit()
    await _value(db, str(external.id), 3_000_000)

    names = {p["name"] for p in (await _candidates(client, buyer, "DEF", "0-5"))["players"]}
    assert names == {"Their Man", "Free Fred"}  # a free agent costs nothing, so fits "up to £5m"


@pytest.mark.asyncio
async def test_free_band_is_free_agents_and_loan_listings(client: AsyncClient, buyer, seller, db):
    from app.players.models import Player, PlayerStatus

    db.add(Player(name="Free Fred", position="MID", status=PlayerStatus.FREE_AGENT, age=26))
    await db.commit()
    loanee = await _player(client, seller, "Loan Lou", position="MID")
    await client.post("/sales", json={"player_id": loanee["id"], "sale_type": "OPEN_TO_OFFERS",
                                      "availability": "LOAN"}, headers=_auth_headers(seller))
    await _value(db, loanee["id"], 12_000_000)
    names = {p["name"] for p in (await _candidates(client, buyer, "ANY", "free"))["players"]}
    assert names == {"Free Fred", "Loan Lou"}


@pytest.mark.asyncio
async def test_a_player_already_in_a_transfer_is_left_out(client: AsyncClient, buyer, seller, db):
    await _give_budget(db)
    busy = await _player(client, seller, "Busy Bill")
    await _value(db, busy["id"], 4_000_000)
    offer = await client.post("/offers", json={
        "player_id": busy["id"], "to_club_id": await _get_club_id(client, _auth_headers(seller)), "fee_amount": 4_000_000,
    }, headers=_auth_headers(buyer))
    await client.post(f"/offers/{offer.json()['id']}/accept", headers=_auth_headers(seller))
    assert (await _candidates(client, buyer, "DEF", "0-5"))["players"] == []


@pytest.mark.asyncio
async def test_the_thinnest_position_ranks_first_for_not_sure(client: AsyncClient, buyer, seller, db):
    for i in range(8):
        await _player(client, buyer, f"My Defender {i}")  # plenty of defenders, no forwards
    d = await _player(client, seller, "Their Defender")
    f = await _player(client, seller, "Their Forward", position="FWD")
    await _value(db, d["id"], 4_000_000)
    await _value(db, f["id"], 4_000_000)
    got = await _candidates(client, buyer, "ANY", "0-5")
    assert got["players"][0]["name"] == "Their Forward"
    assert got["squad_counts"]["DEF"] == 8 and got["squad_counts"]["FWD"] == 0


@pytest.mark.asyncio
async def test_bad_inputs_and_non_members_are_refused(client: AsyncClient, buyer):
    assert (await client.get("/lite/buy/candidates?position=LB&band=5-10", headers=_auth_headers(buyer))).status_code == 422
    assert (await client.get("/lite/buy/candidates?position=DEF&band=lots", headers=_auth_headers(buyer))).status_code == 422
    agent = (await client.post("/auth/register", json={
        "email": "agent_buy@clubs-example.com", "password": "password123", "user_type": "AGENT",
        "display_name": "Buy Agent", "agency_name": "Buy Sports", "country": "England",
    })).json()
    assert (await client.get("/lite/buy/candidates?position=DEF&band=0-5", headers=_auth_headers(agent))).status_code == 404
