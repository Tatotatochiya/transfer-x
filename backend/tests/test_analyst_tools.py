"""The analyst's tools (AI analyst spec §4, §6): right answers, and never
anything the asking club may not see."""
import uuid
from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.ai.analyst.tools import TOOLS, Ctx, run_tool
from app.auth.models import User
from app.clubs.models import Club
from tests.conftest import _auth_headers, _register
from tests.test_deals import _get_club_id, _give_budget
from tests.test_lite_buy import _player

pytestmark = pytest.mark.asyncio


async def _ctx(db, email) -> Ctx:
    user = (await db.execute(select(User).where(User.email == email))).scalar_one()
    club = (await db.execute(select(Club).where(Club.user_id == user.id))).scalar_one()
    return Ctx(db=db, club=club, user=user)


async def _setup(client, db):
    seller = await _register(client, "an_seller@test.com", club_name="Analyst Sellers")
    buyer = await _register(client, "an_buyer@test.com", club_name="Analyst Buyers")
    await _give_budget(db)
    mid = await _player(client, seller, "Marco Midfield", position="MID", age=24)
    other_mid = await _player(client, seller, "Unlisted Mid", position="MID", age=29)
    own_mid = await _player(client, buyer, "Buyers Own Mid", position="MID", age=22)
    for p, club in ((mid, seller), (own_mid, buyer)):
        r = await client.post("/sales", json={"player_id": p["id"], "sale_type": "OPEN_TO_OFFERS",
                                              "asking_price": 6_000_000}, headers=_auth_headers(club))
        assert r.status_code == 201, r.text
    return seller, buyer, mid, other_mid, own_mid


async def test_listed_midfielders_are_other_clubs_and_never_show_wages(client: AsyncClient, db):
    seller, buyer, mid, other_mid, own_mid = await _setup(client, db)
    res = await run_tool(await _ctx(db, "an_buyer@test.com"), "search_players", {"position": "MID", "listed": True, "limit": 5})
    names = [r["player"] for r in res.rows]
    assert names == ["Marco Midfield"]  # listed, another club's; not unlisted, not our own
    row = res.rows[0]
    assert row["listed"] and row["asking_price"] == 6_000_000 and row["path"].startswith("/sales/")
    assert row["club"] == "Analyst Sellers" and row["photo_url"] is None or "photo_url" in row
    assert not any("wage" in k for k in row)
    listings = await run_tool(await _ctx(db, "an_buyer@test.com"), "search_listings", {"position": "MID"})
    assert [r["player"] for r in listings.rows] == ["Marco Midfield"]  # own listing left out by default


async def test_interest_is_counted_for_your_own_players_only_and_never_names_clubs(client: AsyncClient, db):
    from app.players.models import PlayerView
    from app.scouting.models import Shortlist, ShortlistItem

    seller, buyer, mid, other_mid, own_mid = await _setup(client, db)
    seller_club = await _get_club_id(client, _auth_headers(seller))
    await client.post("/enquiries", json={"player_id": mid["id"], "body": "Available?"}, headers=_auth_headers(buyer))
    await client.post("/offers", json={"player_id": mid["id"], "to_club_id": seller_club, "fee_amount": 5_000_000},
                      headers=_auth_headers(buyer))
    buyer_ctx = await _ctx(db, "an_buyer@test.com")
    sl = Shortlist(club_id=buyer_ctx.club.id, name="Targets")
    db.add(sl)
    await db.flush()
    db.add(ShortlistItem(shortlist_id=sl.id, player_id=uuid.UUID(mid["id"])))
    db.add(PlayerView(club_id=buyer_ctx.club.id, player_id=uuid.UUID(mid["id"]), day=date.today(), count=3))
    await db.commit()

    res = await run_tool(await _ctx(db, "an_seller@test.com"), "interest_in_my_players", {"days": 7})
    (row,) = res.rows
    assert row["player"] == "Marco Midfield"
    assert (row["enquiries"], row["offers"], row["shortlisted_by_clubs"], row["viewed_by_clubs"]) == (1, 1, 1, 1)
    assert "Analyst Buyers" not in str(res.for_model())  # counts only, never which clubs
    # The buyer asking the same thing sees only its own players' interest: none.
    assert (await run_tool(buyer_ctx, "interest_in_my_players", {"days": 7})).rows == []


async def test_views_are_recorded_for_other_clubs_only(client: AsyncClient, db):
    from app.players.models import PlayerView

    seller, buyer, mid, other_mid, own_mid = await _setup(client, db)
    await client.get(f"/players/market/{mid['id']}", headers=_auth_headers(buyer))
    await client.get(f"/players/market/{mid['id']}", headers=_auth_headers(buyer))
    await client.get(f"/players/market/{mid['id']}", headers=_auth_headers(seller))  # his own club: not counted
    rows = (await db.execute(select(PlayerView).where(PlayerView.player_id == uuid.UUID(mid["id"])))).scalars().all()
    assert len(rows) == 1 and rows[0].count == 2


async def test_transfers_mask_an_anonymous_buyer_and_money_is_your_own(client: AsyncClient, db):
    seller, buyer, mid, other_mid, own_mid = await _setup(client, db)
    seller_club = await _get_club_id(client, _auth_headers(seller))
    await client.post("/offers", json={"player_id": mid["id"], "to_club_id": seller_club, "fee_amount": 5_000_000,
                                       "is_anonymous": True}, headers=_auth_headers(buyer))
    res = await run_tool(await _ctx(db, "an_seller@test.com"), "transfers", {"your_move": True})
    assert res.rows and "Analyst Buyers" not in str(res.for_model())
    money = await run_tool(await _ctx(db, "an_seller@test.com"), "money", {})
    assert money.kind == "money"


async def test_get_player_says_where_he_is_and_unknown_args_are_ignored(client: AsyncClient, db):
    seller, buyer, mid, other_mid, own_mid = await _setup(client, db)
    res = await run_tool(await _ctx(db, "an_buyer@test.com"), "get_player", {"name": "Midfield", "club_id": "hack"})
    (row,) = res.rows
    assert row["club"] == "Analyst Sellers" and row["is_your_player"] is False and row["listed_for_sale"] is True
    assert (await run_tool(await _ctx(db, "an_buyer@test.com"), "get_player", {"name": "Nobody Atall"})).rows == []
    assert set(TOOLS) >= {"search_players", "get_player", "search_listings", "squad", "money", "transfers", "history",
                          "interest_in_my_players"}
