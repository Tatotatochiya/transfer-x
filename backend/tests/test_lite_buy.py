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


# ── Show more ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_show_more_pages_through_the_same_ranking(client: AsyncClient, buyer, seller, db):
    for i in range(7):
        p = await _player(client, seller, f"Depth Dan {i}", age=25 + i)  # age fit ranks them 0..6
        await _value(db, p["id"], 3_000_000)
    first = await _candidates(client, buyer, "DEF", "0-5")
    assert [p["name"] for p in first["players"]] == ["Depth Dan 0", "Depth Dan 1", "Depth Dan 2"]
    assert first["has_more"] is True
    resp = await client.get("/lite/buy/candidates?position=DEF&band=0-5&offset=3", headers=_auth_headers(buyer))
    second = resp.json()
    assert [p["name"] for p in second["players"]] == ["Depth Dan 3", "Depth Dan 4", "Depth Dan 5"]
    assert second["has_more"] is True
    last = (await client.get("/lite/buy/candidates?position=DEF&band=0-5&offset=6", headers=_auth_headers(buyer))).json()
    assert [p["name"] for p in last["players"]] == ["Depth Dan 6"]
    assert last["has_more"] is False
    bad = await client.get("/lite/buy/candidates?position=DEF&band=0-5&offset=-3", headers=_auth_headers(buyer))
    assert bad.status_code == 422


# ── Search by name ───────────────────────────────────────────────────────────


async def _search(client, club, q):
    resp = await client.get("/lite/buy/search", params={"q": q}, headers=_auth_headers(club))
    assert resp.status_code == 200, resp.text
    return {p["name"]: p for p in resp.json()["players"]}


@pytest.mark.asyncio
async def test_search_finds_everyone_and_says_who_can_be_bought(client: AsyncClient, buyer, seller, db):
    from app.players.models import Player, PlayerStatus

    theirs = await _player(client, seller, "Search Theirs")
    await _value(db, theirs["id"], 7_000_000)
    unpriced = await _player(client, seller, "Search Unpriced")
    await _player(client, buyer, "Search Mine")
    db.add_all([
        Player(name="Search Elsewhere", position="DEF", status=PlayerStatus.EXTERNAL, team_name="Real Somewhere"),
        Player(name="Search Free", position="DEF", status=PlayerStatus.FREE_AGENT, age=27),
    ])
    await db.commit()

    got = await _search(client, buyer, "search")
    assert got["Search Theirs"]["state"] == "buyable"
    assert (got["Search Theirs"]["price"], got["Search Theirs"]["club"]) == (7_000_000, "Selling FC")
    assert got["Search Unpriced"]["state"] == "buyable" and got["Search Unpriced"]["price"] is None
    assert got["Search Unpriced"]["player_id"] == unpriced["id"]
    assert got["Search Mine"]["state"] == "yours"
    assert got["Search Elsewhere"]["state"] == "outside"
    assert got["Search Elsewhere"]["club"] == "Real Somewhere" and got["Search Elsewhere"]["price"] is None
    assert got["Search Free"]["state"] == "free_agent" and got["Search Free"]["club"] is None
    # Players the club can act on come first.
    states = [p["state"] for p in got.values()]
    assert states.index("buyable") < states.index("free_agent") < states.index("outside") < states.index("yours")


@pytest.mark.asyncio
async def test_search_marks_an_open_offer_and_a_transfer_in_progress(client: AsyncClient, buyer, seller, db):
    rival = await _register(client, "rival_buy@clubs-example.com", club_name="Rival FC")
    await _give_budget(db)
    seller_id = await _get_club_id(client, _auth_headers(seller))
    mine = await _player(client, seller, "Offered Olly")
    offer = (await client.post("/offers", json={"player_id": mine["id"], "to_club_id": seller_id, "fee_amount": 2_000_000},
                               headers=_auth_headers(buyer))).json()
    busy = await _player(client, seller, "Offered Busy")
    other = (await client.post("/offers", json={"player_id": busy["id"], "to_club_id": seller_id, "fee_amount": 2_000_000},
                               headers=_auth_headers(rival))).json()
    await client.post(f"/offers/{other['id']}/accept", headers=_auth_headers(seller))

    got = await _search(client, buyer, "offered")
    assert got["Offered Olly"]["state"] == "offer_in" and got["Offered Olly"]["offer_id"] == offer["id"]
    assert got["Offered Busy"]["state"] == "in_transfer"


@pytest.mark.asyncio
async def test_search_ranks_a_word_of_the_name_first(client: AsyncClient, buyer, seller, db):
    from app.players.models import Player, PlayerStatus

    await _player(client, seller, "A. Harrison")  # buyable, but "son" is inside a word
    db.add(Player(name="H. Son", position="FWD", status=PlayerStatus.EXTERNAL, team_name="Spurs Abroad"))
    await db.commit()
    resp = await client.get("/lite/buy/search", params={"q": "son"}, headers=_auth_headers(buyer))
    assert [p["name"] for p in resp.json()["players"]] == ["H. Son", "A. Harrison"]


@pytest.mark.asyncio
async def test_search_hides_private_players_and_treats_wildcards_literally(client: AsyncClient, buyer, seller, db):
    from app.players.models import Player, PlayerVisibility

    hidden = await _player(client, seller, "Hidden Harry")
    row = await db.get(Player, uuid.UUID(hidden["id"]))
    row.visibility = PlayerVisibility.PRIVATE
    await db.commit()
    await _player(client, seller, "Percy Plain")

    assert await _search(client, buyer, "hidden") == {}
    assert await _search(client, buyer, "%%") == {}  # not "match everything"
    assert set(await _search(client, buyer, "percy")) == {"Percy Plain"}


@pytest.mark.asyncio
async def test_search_needs_two_letters_a_club_and_a_sign_in(client: AsyncClient, buyer):
    assert (await client.get("/lite/buy/search?q=a", headers=_auth_headers(buyer))).status_code == 422
    agent = (await client.post("/auth/register", json={
        "email": "agent_search@clubs-example.com", "password": "password123", "user_type": "AGENT",
        "display_name": "Search Agent", "agency_name": "Search Sports", "country": "England",
    })).json()
    assert (await client.get("/lite/buy/search?q=ab", headers=_auth_headers(agent))).status_code == 404
    assert (await client.get("/lite/buy/search?q=ab")).status_code == 401
    # The app-wide search no longer answers signed-out callers either.
    assert (await client.get("/search?q=ab")).status_code == 401
    assert (await client.get("/search?q=ab", headers=_auth_headers(buyer))).status_code == 200
