"""A listing can shut out clubs, by name or by domestic league. While it is
open, an excluded club can't make any offer for the player and isn't told why
or that it was excluded; only the seller and staff see the list."""
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from tests.conftest import _auth_headers, _register
from tests.test_offers import _create_player, _get_seller_club_id, _give_budget

pytestmark = pytest.mark.asyncio


async def _set_league(db, club_id: str, league: str) -> None:
    from app.clubs.models import Club

    club = (await db.execute(select(Club).where(Club.id == uuid.UUID(club_id)))).scalar_one()
    club.league_name = league
    await db.commit()


async def _list(client, headers, player_id, **extra):
    return await client.post("/sales", json={"player_id": player_id, "sale_type": "OPEN_TO_OFFERS", **extra}, headers=headers)


async def _offer(client, headers, player_id, seller_id, sale_id=None):
    body = {"player_id": player_id, "to_club_id": seller_id, "fee_amount": 10_000_000}
    if sale_id:
        body["sale_id"] = sale_id
    return await client.post("/offers", json=body, headers=headers)


@pytest.fixture
async def market(client: AsyncClient, db):
    seller = await _register(client, "ex_seller@test.com", club_name="Seller FC")
    rival = await _register(client, "ex_rival@test.com", club_name="Rival FC")
    other = await _register(client, "ex_other@test.com", club_name="Other FC")
    await _give_budget(db)
    player = await _create_player(client, _auth_headers(seller), name="Kept Away")
    return {
        "seller": seller, "rival": rival, "other": other, "player": player["id"],
        "seller_id": await _get_seller_club_id(client, _auth_headers(seller)),
        "rival_id": await _get_seller_club_id(client, _auth_headers(rival)),
        "other_id": await _get_seller_club_id(client, _auth_headers(other)),
    }


async def test_an_excluded_club_cannot_offer_with_or_without_the_listing(client: AsyncClient, market):
    m = market
    r = await _list(client, _auth_headers(m["seller"]), m["player"], excluded_club_ids=[m["rival_id"]])
    assert r.status_code == 201, r.text
    sale_id = r.json()["id"]
    assert [c["name"] for c in r.json()["excluded_clubs"]] == ["Rival FC"]

    for via in (sale_id, None):
        r = await _offer(client, _auth_headers(m["rival"]), m["player"], m["seller_id"], via)
        assert r.status_code == 400
        assert r.json()["detail"] == "His club isn't taking offers from your club for him."
    r = await _offer(client, _auth_headers(m["other"]), m["player"], m["seller_id"], sale_id)
    assert r.status_code == 201, r.text


async def test_a_league_exclusion_ignores_case_and_ends_with_the_listing(client: AsyncClient, db, market):
    m = market
    await _set_league(db, m["rival_id"], "Premier League")
    await _set_league(db, m["other_id"], "Championship")
    r = await _list(client, _auth_headers(m["seller"]), m["player"], excluded_leagues=[" premier league ", "Premier League"])
    assert r.status_code == 201, r.text
    assert r.json()["excluded_leagues"] == ["premier league"]

    assert (await _offer(client, _auth_headers(m["rival"]), m["player"], m["seller_id"])).status_code == 400
    assert (await _offer(client, _auth_headers(m["other"]), m["player"], m["seller_id"])).status_code == 201

    # Withdrawn: he isn't listed, and the exclusion goes with the listing.
    r = await client.post(f"/sales/{r.json()['id']}/withdraw", headers=_auth_headers(m["seller"]))
    assert r.status_code == 200, r.text
    assert (await _offer(client, _auth_headers(m["rival"]), m["player"], m["seller_id"])).status_code == 201


async def test_only_the_seller_sees_who_is_excluded(client: AsyncClient, db, market):
    m = market
    r = await _list(client, _auth_headers(m["seller"]), m["player"],
                    excluded_club_ids=[m["rival_id"]], excluded_leagues=["Serie A"])
    sale_id = r.json()["id"]

    mine = (await client.get(f"/sales/{sale_id}", headers=_auth_headers(m["seller"]))).json()
    assert [c["id"] for c in mine["excluded_clubs"]] == [m["rival_id"]]
    assert mine["excluded_leagues"] == ["Serie A"]
    for viewer in ("rival", "other"):
        theirs = (await client.get(f"/sales/{sale_id}", headers=_auth_headers(m[viewer]))).json()
        assert theirs["excluded_clubs"] == [] and theirs["excluded_leagues"] == []
    listed = (await client.get("/sales", headers=_auth_headers(m["rival"]))).json()["items"]
    assert all(s["excluded_clubs"] == [] for s in listed)


async def test_a_seller_cannot_exclude_itself_or_an_unknown_club(client: AsyncClient, market):
    m = market
    r = await _list(client, _auth_headers(m["seller"]), m["player"], excluded_club_ids=[m["seller_id"]])
    assert r.status_code == 400 and "own club" in r.json()["detail"]
    r = await _list(client, _auth_headers(m["seller"]), m["player"], excluded_club_ids=[str(uuid.uuid4())])
    assert r.status_code == 400


async def test_an_excluded_club_is_not_told_he_is_available(client: AsyncClient, db, market):
    from app.auth.models import User
    from app.notifications.models import Notification, NotificationType
    from app.scouting.models import Shortlist, ShortlistItem

    m = market
    for key in ("rival_id", "other_id"):
        sl = Shortlist(club_id=uuid.UUID(m[key]), name="Targets")
        db.add(sl)
        await db.flush()
        db.add(ShortlistItem(shortlist_id=sl.id, player_id=uuid.UUID(m["player"])))
    await db.commit()

    r = await _list(client, _auth_headers(m["seller"]), m["player"], excluded_club_ids=[m["rival_id"]])
    assert r.status_code == 201, r.text

    async def told(email):
        db.expire_all()
        uid = (await db.execute(select(User.id).where(User.email == email))).scalar_one()
        return (await db.execute(select(Notification).where(
            Notification.recipient_user_id == uid, Notification.type == NotificationType.PLAYER_AVAILABLE,
        ))).scalars().all()

    assert await told("ex_rival@test.com") == []
    assert len(await told("ex_other@test.com")) == 1


async def test_the_league_picker_lists_domestic_leagues_only(client: AsyncClient, db, market):
    m = market
    await _set_league(db, m["rival_id"], "Premier League")
    await _set_league(db, m["other_id"], "UEFA Champions League")
    r = await client.get("/clubs/leagues", headers=_auth_headers(m["seller"]))
    assert r.status_code == 200, r.text
    assert r.json() == ["Premier League"]
