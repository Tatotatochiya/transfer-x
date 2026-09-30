"""Lite home read model (docs/feature_spec/lite-mode, BACKEND.md §2)."""

from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient

from tests.conftest import _auth_headers, _register
from tests.test_deals import _create_player_for_seller, _get_club_id, _give_budget


async def _home(client, tokens):
    resp = await client.get("/lite/home", headers=_auth_headers(tokens))
    assert resp.status_code == 200, resp.text
    return resp.json()


async def _window(db, *, opens_in_days: int, lasts_days: int = 30):
    from app.transfer_window.models import TransferWindow

    now = datetime.now(timezone.utc)
    db.add(TransferWindow(name="Test window", opens_at=now + timedelta(days=opens_in_days),
                          closes_at=now + timedelta(days=opens_in_days + lasts_days)))
    await db.commit()


@pytest.fixture
def no_model(monkeypatch):
    """Any model call from the home screen fails the test."""
    from app.ai import assist

    async def boom(*a, **k):
        raise AssertionError("the Lite home must never call a model")

    monkeypatch.setattr(assist, "_llm_json", boom)
    monkeypatch.setattr(assist, "chat", boom)


@pytest.mark.asyncio
async def test_no_window_configured_shows_the_buying_tiles(client: AsyncClient, no_model):
    club = await _register(client, "home_lite@clubs-example.com", club_name="Home FC")
    home = await _home(client, club)
    assert home["window"]["state"] == "none"
    assert [t["key"] for t in home["tiles"]] == ["buy", "sell", "offers", "ask"]
    assert home["money"]["transfer_budget"] >= 0


@pytest.mark.asyncio
async def test_open_window_counts_days_to_close(client: AsyncClient, db, no_model):
    await _window(db, opens_in_days=-5, lasts_days=17)
    club = await _register(client, "home_lite@clubs-example.com", club_name="Home FC")
    home = await _home(client, club)
    assert home["window"]["state"] == "open"
    assert home["window"]["days"] in (11, 12)
    assert [t["key"] for t in home["tiles"]] == ["buy", "sell", "offers", "ask"]


@pytest.mark.asyncio
async def test_closed_window_shows_the_seasonal_tiles(client: AsyncClient, db, no_model):
    await _window(db, opens_in_days=95)
    club = await _register(client, "home_lite@clubs-example.com", club_name="Home FC")
    home = await _home(client, club)
    assert home["window"]["state"] == "closed"
    assert home["window"]["days"] in (94, 95)
    assert [t["key"] for t in home["tiles"]] == ["renew", "plan", "squad", "ask"]


@pytest.mark.asyncio
async def test_waiting_matches_the_war_room_and_masks_anonymous_buyers(client: AsyncClient, db, no_model):
    buyer = await _register(client, "buyer_home@clubs-example.com", club_name="Hidden Buyer FC")
    seller = await _register(client, "seller_home@clubs-example.com", club_name="Selling FC")
    await _give_budget(db)
    player = await _create_player_for_seller(client, _auth_headers(seller))
    await client.post("/offers", json={
        "player_id": player["id"], "to_club_id": await _get_club_id(client, _auth_headers(seller)),
        "fee_amount": 5_000_000, "is_anonymous": True,
    }, headers=_auth_headers(buyer))

    home = await _home(client, seller)
    war_room = (await client.get("/clubs/me/dashboard", headers=_auth_headers(seller))).json()["waiting_on_you"]
    assert home["waiting"]["count"] == len(war_room) == 1
    assert "Hidden Buyer" not in str(home)
    offers = next(t for t in home["tiles"] if t["key"] == "offers")
    assert offers["badge"] == "1 waiting"


@pytest.mark.asyncio
async def test_closed_window_with_offers_waiting_swaps_squad_for_offers(client: AsyncClient, db, no_model):
    await _window(db, opens_in_days=60)
    buyer = await _register(client, "buyer_home@clubs-example.com", club_name="Buying FC")
    seller = await _register(client, "seller_home@clubs-example.com", club_name="Selling FC")
    await _give_budget(db)
    player = await _create_player_for_seller(client, _auth_headers(seller))
    # Enquiries are allowed outside the window, and they wait on the seller.
    await client.post("/enquiries", json={"player_id": player["id"], "body": "Would you sell?"},
                      headers=_auth_headers(buyer))
    home = await _home(client, seller)
    assert [t["key"] for t in home["tiles"]] == ["renew", "plan", "offers", "ask"]


@pytest.mark.asyncio
async def test_resume_is_saved_expires_and_clears(client: AsyncClient, db, no_model):
    from app.lite.models import UserPreference
    from sqlalchemy import select

    club = await _register(client, "home_lite@clubs-example.com", club_name="Home FC")
    h = _auth_headers(club)
    assert (await client.put("/lite/resume", json={"title": "Defender search", "href": "/lite/buy/results?position=DEF"},
                             headers=h)).status_code == 204
    assert (await _home(client, club))["resume"] == {"title": "Defender search", "href": "/lite/buy/results?position=DEF"}

    # Only Lite pages can be resumed.
    assert (await client.put("/lite/resume", json={"title": "x", "href": "/admin"}, headers=h)).status_code == 422

    # Older than 14 days: gone.
    row = (await db.execute(select(UserPreference))).scalar_one()
    row.lite_resume_json = {**row.lite_resume_json, "at": (datetime.now(timezone.utc) - timedelta(days=15)).isoformat()}
    await db.commit()
    assert (await _home(client, club))["resume"] is None

    await client.put("/lite/resume", json={"title": "Again", "href": "/lite/buy"}, headers=h)
    assert (await client.delete("/lite/resume", headers=h)).status_code == 204
    assert (await _home(client, club))["resume"] is None


@pytest.mark.asyncio
async def test_lite_home_is_for_club_members(client: AsyncClient):
    agent = (await client.post("/auth/register", json={
        "email": "agent_home@clubs-example.com", "password": "password123", "user_type": "AGENT",
        "display_name": "Home Agent", "agency_name": "Home Sports", "country": "England",
    })).json()
    assert (await client.get("/lite/home", headers=_auth_headers(agent))).status_code == 404
