"""Lite Buy page: search by name, the club's targets and its shortlist
(docs/feature_spec/lite-mode, BACKEND.md §2a)."""

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
    """The Buy page never calls a model; make sure it can't."""
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


@pytest.mark.asyncio
async def test_search_prices_from_the_listing_else_the_model(client: AsyncClient, buyer, seller, db):
    listed = await _player(client, seller, "Priced Listed")
    await client.post("/sales", json={"player_id": listed["id"], "sale_type": "OPEN_TO_OFFERS", "asking_price": 6_000_000},
                      headers=_auth_headers(seller))
    modelled = await _player(client, seller, "Priced Modelled")
    await _value(db, modelled["id"], 8_000_000)
    got = await _search(client, buyer, "priced")
    assert (got["Priced Listed"]["price"], got["Priced Listed"]["price_basis"]) == (6_000_000, "listed")
    assert (got["Priced Modelled"]["price"], got["Priced Modelled"]["price_basis"]) == (8_000_000, "model")


# ── Targets and the shortlist ────────────────────────────────────────────────


async def _targets(client, club):
    resp = await client.get("/lite/buy/targets", headers=_auth_headers(club))
    assert resp.status_code == 200, resp.text
    return resp.json()


@pytest.mark.asyncio
async def test_shortlist_from_lite_then_targets_show_him(client: AsyncClient, buyer, seller, db):
    assert await _targets(client, buyer) == {"players": [], "total": 0}
    target = await _player(client, seller, "Target Tom")
    await _value(db, target["id"], 4_000_000)

    put = await client.put(f"/lite/buy/shortlist/{target['id']}", headers=_auth_headers(buyer))
    assert put.status_code == 204, put.text
    # Twice changes nothing.
    assert (await client.put(f"/lite/buy/shortlist/{target['id']}", headers=_auth_headers(buyer))).status_code == 204

    got = await _targets(client, buyer)
    [row] = got["players"]
    assert (row["name"], row["state"], row["price"], row["on_shortlists"]) == ("Target Tom", "buyable", 4_000_000, ["Shortlist"])
    assert (await _search(client, buyer, "target"))["Target Tom"]["shortlisted"] is True
    # It's an ordinary shortlist in full mode.
    lists = (await client.get("/scouting/shortlists", headers=_auth_headers(buyer))).json()
    assert [sl["name"] for sl in lists] == ["Shortlist"]

    assert (await client.delete(f"/lite/buy/shortlist/{target['id']}", headers=_auth_headers(buyer))).status_code == 204
    assert (await _targets(client, buyer))["players"] == []
    assert (await _search(client, buyer, "target"))["Target Tom"]["shortlisted"] is False


@pytest.mark.asyncio
async def test_targets_include_full_mode_lists_and_interest_but_not_own_players(client: AsyncClient, buyer, seller, db):
    on_list = await _player(client, seller, "Listed Liam")
    watched = await _player(client, seller, "Watched Walt")
    mine = await _player(client, buyer, "Own Oscar")
    h = _auth_headers(buyer)
    sl = (await client.post("/scouting/shortlists", json={"name": "Strikers"}, headers=h)).json()
    for pid in (on_list["id"], mine["id"]):
        assert (await client.post(f"/scouting/shortlists/{sl['id']}/items", json={"player_id": pid}, headers=h)).status_code == 201
    assert (await client.put(f"/scouting/interests/{watched['id']}", json={"level": "WATCHING", "stage": "SCOUTED"}, headers=h)).status_code == 200

    got = {p["name"]: p for p in (await _targets(client, buyer))["players"]}
    assert set(got) == {"Listed Liam", "Watched Walt"}
    assert got["Listed Liam"]["on_shortlists"] == ["Strikers"] and got["Watched Walt"]["on_shortlists"] == []
    # Taking him off in Lite takes him off the full-mode list too; interest stays.
    await client.delete(f"/lite/buy/shortlist/{on_list['id']}", headers=h)
    assert {p["name"] for p in (await _targets(client, buyer))["players"]} == {"Watched Walt"}


@pytest.mark.asyncio
async def test_shortlist_needs_a_visible_player_and_scouting_rights(client: AsyncClient, buyer, seller, db):
    from app.players.models import Player, PlayerVisibility

    hidden = await _player(client, seller, "Secret Sam")
    row = await db.get(Player, uuid.UUID(hidden["id"]))
    row.visibility = PlayerVisibility.PRIVATE
    await db.commit()
    h = _auth_headers(buyer)
    assert (await client.put(f"/lite/buy/shortlist/{hidden['id']}", headers=h)).status_code == 404
    assert (await client.put(f"/lite/buy/shortlist/{uuid.uuid4()}", headers=h)).status_code == 404
    assert (await client.get("/lite/buy/targets")).status_code == 401
    # A read-only member sees the targets but can't change the shortlist.
    from tests.test_capabilities import _create_staff

    readonly = await _create_staff(client, db, h, "buy_ro@clubs-example.com", "READONLY")
    assert (await client.get("/lite/buy/targets", headers=_auth_headers(readonly))).status_code == 200
    visible = await _player(client, seller, "Open Owen")
    assert (await client.put(f"/lite/buy/shortlist/{visible['id']}", headers=_auth_headers(readonly))).status_code == 403
    # The guided path is gone.
    assert (await client.get("/lite/buy/candidates?position=DEF&band=0-5", headers=h)).status_code == 404
