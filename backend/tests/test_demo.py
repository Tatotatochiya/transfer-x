"""Demo mode: runs, the change journal and reset (app/demo)."""
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select, update

from app.config import settings
from tests.conftest import _auth_headers, _register
from tests.test_deals import _create_player_for_seller, _get_club_id, _get_finance, _give_budget

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def demo_on(monkeypatch):
    monkeypatch.setattr(settings, "demo_enabled", True)


async def _staff(client, db, email="demo_staff@demo-example.com"):
    from app.auth.models import User

    tokens = await _register(client, email, club_name="Demo Staff FC")
    user = (await db.execute(select(User).where(User.email == email))).scalar_one()
    user.is_superuser = True
    await db.commit()
    return tokens


async def _house(db, tokens):
    """Make a registered club a house club (as if nobody had used it)."""
    from app.auth.models import User
    from app.clubs.models import Club

    club = (await db.execute(select(Club).join(User, User.id == Club.user_id)
                             .where(User.email == tokens["email"]))).scalar_one()
    club.house_club, club.house_personality = True, "fair"
    await db.commit()
    return club


@pytest_asyncio.fixture
async def setup(client: AsyncClient, db) -> dict:
    tester = await _register(client, "tester@demo-example.com", club_name="Tester FC")
    house = await _register(client, "house@demo-example.com", club_name="House United")
    real = await _register(client, "real@demo-example.com", club_name="Real Rovers")
    for t, e in ((tester, "tester@demo-example.com"), (house, "house@demo-example.com"), (real, "real@demo-example.com")):
        t["email"] = e
    staff = await _staff(client, db)
    await _give_budget(db)
    from app.auth.models import User

    (await db.execute(select(User).where(User.email == "tester@demo-example.com"))).scalar_one().can_demo = True
    await db.commit()
    await _house(db, house)
    return {"tester": tester, "house": house, "real": real, "staff": staff}


async def _start(client, tokens):
    resp = await client.post("/demo/run", headers=_auth_headers(tokens))
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _play_as(client, tester, club_id) -> dict:
    resp = await client.post(f"/demo/house-clubs/{club_id}/play-as", headers=_auth_headers(tester))
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def test_only_testers_and_staff_can_start_and_only_one_at_a_time(client: AsyncClient, db, setup, monkeypatch):
    real_me = (await client.get("/auth/me", headers=_auth_headers(setup["real"]))).json()
    assert real_me["can_demo"] is False
    assert (await client.post("/demo/run", headers=_auth_headers(setup["real"]))).status_code == 403
    assert (await client.get("/auth/me", headers=_auth_headers(setup["tester"]))).json()["can_demo"] is True
    run = await _start(client, setup["tester"])
    assert run["status"] == "ACTIVE" and run["changes"] == 0 and run["resets_on"]
    assert (await client.post("/demo/run", headers=_auth_headers(setup["tester"]))).status_code == 409
    await _start(client, setup["staff"])  # staff always may
    monkeypatch.setattr(settings, "demo_enabled", False)
    assert (await client.get("/demo/run", headers=_auth_headers(setup["tester"]))).json() == {"can_demo": False, "run": None}


async def test_a_whole_buy_played_by_hand_is_put_back_by_reset(client: AsyncClient, db, setup):
    from app.deals.models import Deal
    from app.notifications.models import Notification
    from app.offers.models import Offer

    tester, house = setup["tester"], setup["house"]
    player = await _create_player_for_seller(client, _auth_headers(house))
    house_id = await _get_club_id(client, _auth_headers(house))
    before = await _get_finance(client, _auth_headers(tester))
    notes_before = (await db.execute(select(Notification.id))).scalars().all()

    await _start(client, tester)
    offer = await client.post("/offers", headers=_auth_headers(tester), json={
        "player_id": player["id"], "to_club_id": house_id, "fee_amount": 3_000_000})
    assert offer.status_code == 201, offer.text
    # The tester plays the house club in its own tab, inside the demo.
    as_house = await _play_as(client, tester, house_id)
    me = (await client.get("/auth/me", headers=as_house)).json()
    assert me["demo_played_by"] and me["email"] == "house@demo-example.com"
    accepted = await client.post(f"/offers/{offer.json()['id']}/accept", headers=as_house)
    assert accepted.status_code == 200, accepted.text
    assert float((await _get_finance(client, _auth_headers(tester)))["transfer_committed"]) == 3_000_000
    run = (await client.get("/demo/run", headers=_auth_headers(tester))).json()["run"]
    assert run["changes"] > 3

    report = (await client.post("/demo/run/reset", headers=_auth_headers(tester))).json()
    assert report["skipped"] == [] and report["undone"] > 3
    db.expire_all()
    assert (await db.execute(select(Offer))).scalars().all() == []
    assert (await db.execute(select(Deal))).scalars().all() == []
    assert (await db.execute(select(Notification.id))).scalars().all() == notes_before
    after = await _get_finance(client, _auth_headers(tester))
    assert after["transfer_committed"] == before["transfer_committed"]
    assert (await client.get("/demo/run", headers=_auth_headers(tester))).json()["run"] is None
    # The play-as tab ends with the demo.
    assert (await client.get("/auth/me", headers=as_house)).status_code == 401


async def test_reset_leaves_a_real_change_made_since(client: AsyncClient, db, setup):
    from app.clubs.models import Club

    tester = setup["tester"]
    club_id = uuid.UUID(await _get_club_id(client, _auth_headers(tester)))
    city_before = (await db.get(Club, club_id)).city
    await _start(client, tester)
    resp = await client.patch("/clubs/me", headers=_auth_headers(tester), json={"city": "Demo City", "country": "Demoland"})
    assert resp.status_code == 200, resp.text
    # Something real changes the country after the demo did (in its own
    # session in real life; the tests share one, so leave the run first).
    db.sync_session.info.pop("demo_run_id", None)
    await db.execute(update(Club).where(Club.id == club_id).values(country="Realland"))
    await db.commit()

    report = (await client.post("/demo/run/reset", headers=_auth_headers(tester))).json()
    db.expire_all()
    club = await db.get(Club, club_id)
    assert club.city == city_before  # put back
    assert club.country == "Realland"  # left: changed since the demo
    [skip] = report["skipped"]
    assert skip["table"] == "clubs" and "country" in skip["why"]


async def test_bulk_updates_and_jobs_touching_demo_rows_are_journaled(client: AsyncClient, db, setup):
    from app.demo import service as demo_service
    from app.demo.models import DemoRun
    from app.offers.models import Offer, OfferStatus

    tester, house = setup["tester"], setup["house"]
    player = await _create_player_for_seller(client, _auth_headers(house))
    house_id = await _get_club_id(client, _auth_headers(house))
    run = await _start(client, tester)
    offer = (await client.post("/offers", headers=_auth_headers(tester), json={
        "player_id": player["id"], "to_club_id": house_id, "fee_amount": 2_000_000})).json()

    # A job, with no run of its own, expires the demo offer in a bulk update:
    # it joins the run because the row is the demo's.
    db.sync_session.info.pop("demo_run_id", None)
    await db.execute(update(Offer).where(Offer.id == uuid.UUID(offer["id"])).values(status=OfferStatus.EXPIRED))
    await db.commit()
    assert "demo_run_id" not in db.sync_session.info  # left again when the transaction ended

    row = await db.get(DemoRun, uuid.UUID(run["id"]))
    report = await demo_service.reset(db, row, by_user_id=None)
    await db.commit()
    assert report["skipped"] == []
    db.expire_all()
    assert (await db.execute(select(Offer))).scalars().all() == []


async def test_in_a_demo_only_house_clubs_are_dealt_with(client: AsyncClient, db, setup):
    tester, real = setup["tester"], setup["real"]
    real_player = await _create_player_for_seller(client, _auth_headers(real))
    real_id = await _get_club_id(client, _auth_headers(real))
    await _start(client, tester)
    refused = await client.post("/offers", headers=_auth_headers(tester), json={
        "player_id": real_player["id"], "to_club_id": real_id, "fee_amount": 2_000_000})
    assert refused.status_code == 409 and "Real Rovers isn't one" in refused.text
    enquiry = await client.post("/enquiries", headers=_auth_headers(tester), json={
        "player_id": real_player["id"], "body": "Is he available?"})
    assert enquiry.status_code == 409
    # Outside a demo, the same offer goes through.
    await client.post("/demo/run/keep", headers=_auth_headers(tester))
    ok = await client.post("/offers", headers=_auth_headers(tester), json={
        "player_id": real_player["id"], "to_club_id": real_id, "fee_amount": 2_000_000})
    assert ok.status_code == 201, ok.text


async def test_nobody_outside_a_demo_bids_on_its_listing(client: AsyncClient, db, setup):
    tester, real = setup["tester"], setup["real"]
    mine = await _create_player_for_seller(client, _auth_headers(tester))
    await _start(client, tester)
    sale = await client.post("/sales", headers=_auth_headers(tester), json={
        "player_id": mine["id"], "sale_type": "OPEN_TO_OFFERS", "asking_price": 4_000_000})
    assert sale.status_code == 201, sale.text
    bid = await client.post(f"/sales/{sale.json()['id']}/bids", headers=_auth_headers(real), json={"amount": 4_000_000})
    assert bid.status_code == 409 and "part of someone's demo" in bid.text


async def test_runs_left_open_two_weeks_reset_themselves(client: AsyncClient, db, setup):
    from app.clubs.models import Club
    from app.demo import service as demo_service
    from app.demo.models import DemoRun

    tester = setup["tester"]
    club_id = uuid.UUID(await _get_club_id(client, _auth_headers(tester)))
    city_before = (await db.get(Club, club_id)).city
    run = await _start(client, tester)
    await client.patch("/clubs/me", headers=_auth_headers(tester), json={"city": "Forgotten"})
    row = await db.get(DemoRun, uuid.UUID(run["id"]))
    row.started_at = datetime.now(timezone.utc) - timedelta(days=15)
    await db.commit()
    assert await demo_service.auto_reset(db) == 1
    db.expire_all()
    assert (await db.get(Club, club_id)).city == city_before
    assert (await db.get(DemoRun, uuid.UUID(run["id"]))).status == "RESET"


async def test_staff_choose_house_clubs_and_testers(client: AsyncClient, db, setup):
    from app.auth.models import User
    from app.clubs.models import Club

    staff = _auth_headers(setup["staff"])
    real_id = await _get_club_id(client, _auth_headers(setup["real"]))
    owner = (await db.execute(select(User).where(User.email == "real@demo-example.com"))).scalar_one()
    owner.last_active_at = datetime.now(timezone.utc)
    await db.commit()
    # Real Rovers' owner has used TransferX, so it's in use.
    overview = (await client.get("/admin/demo", headers=staff)).json()
    rovers = next(c for c in overview["clubs"] if c["name"] == "Real Rovers")
    assert rovers["in_use"] is True and overview["enabled"] is True
    refused = await client.patch(f"/admin/demo/clubs/{real_id}", headers=staff,
                                 json={"house_club": True, "reason": "For the Friday demo"})
    assert refused.status_code == 409

    owner.last_active_at = None
    await db.commit()
    ok = await client.patch(f"/admin/demo/clubs/{real_id}", headers=staff,
                            json={"house_club": True, "personality": "hard", "reason": "For the Friday demo"})
    assert ok.status_code == 200, ok.text
    db.expire_all()
    assert (await db.get(Club, uuid.UUID(real_id))).house_personality == "hard"
    houses = (await client.get("/demo/house-clubs", headers=_auth_headers(setup["tester"]))).json()
    assert {h["name"] for h in houses} == {"House United", "Real Rovers"}

    tester_id = (await db.execute(select(User.id).where(User.email == "tester@demo-example.com"))).scalar_one()
    off = await client.patch(f"/admin/demo/testers/{tester_id}", headers=staff,
                             json={"can_demo": False, "reason": "Testing finished"})
    assert off.status_code == 200
    assert (await client.post("/demo/run", headers=_auth_headers(setup["tester"]))).status_code == 403
    # Not for clubs.
    assert (await client.get("/admin/demo", headers=_auth_headers(setup["tester"]))).status_code == 403


async def test_staff_can_reset_anyones_demo(client: AsyncClient, db, setup):
    run = await _start(client, setup["tester"])
    resp = await client.post(f"/admin/demo/runs/{run['id']}/reset", headers=_auth_headers(setup["staff"]))
    assert resp.status_code == 200, resp.text
    again = await client.post(f"/admin/demo/runs/{run['id']}/reset", headers=_auth_headers(setup["staff"]))
    assert again.status_code == 409
