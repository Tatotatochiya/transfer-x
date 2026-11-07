"""Transfer windows per country (app/transfer_window): deals run all year,
and a closed window holds only completion."""

import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select

from tests.conftest import _auth_headers, _register
from tests.test_deals import _create_player_for_seller, _get_club_id, _give_budget


async def _window(db, *, country=None, opens_in_days: float, lasts_days: float = 30, name="January 2027"):
    from app.transfer_window.models import TransferWindow

    now = datetime.now(timezone.utc)
    w = TransferWindow(name=name, country=country, opens_at=now + timedelta(days=opens_in_days),
                       closes_at=now + timedelta(days=opens_in_days + lasts_days))
    db.add(w)
    await db.commit()
    return w


async def _set_country(db, club_id, country):
    from app.clubs.models import Club

    club = await db.get(Club, uuid.UUID(str(club_id)))
    club.country = country
    await db.commit()


@pytest_asyncio.fixture
async def market(client: AsyncClient, db) -> dict:
    """An English buyer and seller, and a player the seller owns."""
    buyer = await _register(client, "buyer_tw@clubs-example.com", club_name="Buying FC")
    seller = await _register(client, "seller_tw@clubs-example.com", club_name="Selling FC")
    await _give_budget(db)
    out = {"buyer": buyer, "seller": seller,
           "buyer_id": await _get_club_id(client, _auth_headers(buyer)),
           "seller_id": await _get_club_id(client, _auth_headers(seller))}
    for key in ("buyer_id", "seller_id"):
        await _set_country(db, out[key], "England")
    out["player"] = await _create_player_for_seller(client, _auth_headers(seller))
    return out


async def _confirmed_deal(client, db, market) -> str:
    """An accepted offer, moved on to CONFIRMED: only completion is left."""
    from app.deals.models import Deal, DealStage, DealStatus

    offer = await client.post("/offers", headers=_auth_headers(market["buyer"]), json={
        "player_id": market["player"]["id"], "to_club_id": market["seller_id"], "fee_amount": 2_000_000})
    assert offer.status_code == 201, offer.text
    accepted = await client.post(f"/offers/{offer.json()['id']}/accept", headers=_auth_headers(market["seller"]))
    assert accepted.status_code == 200, accepted.text
    deal = (await db.execute(select(Deal).where(Deal.player_id == uuid.UUID(market["player"]["id"])))).scalar_one()
    deal.stage, deal.status = DealStage.CONFIRMED, DealStatus.PENDING_COMPLETION
    deal.sla_deadline = datetime.now(timezone.utc) + timedelta(days=14)
    await db.commit()
    return str(deal.id)


# ── Deals run all year ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_offers_and_listings_go_ahead_while_the_window_is_closed(client: AsyncClient, db, market):
    await _window(db, country="England", opens_in_days=50)
    offer = await client.post("/offers", headers=_auth_headers(market["buyer"]), json={
        "player_id": market["player"]["id"], "to_club_id": market["seller_id"], "fee_amount": 2_000_000})
    assert offer.status_code == 201, offer.text

    other = await _create_player_for_seller(client, _auth_headers(market["seller"]))
    sale = await client.post("/sales", headers=_auth_headers(market["seller"]), json={
        "player_id": other["id"], "sale_type": "FIXED_PRICE", "asking_price": 5_000_000})
    assert sale.status_code == 201, sale.text


@pytest.mark.asyncio
async def test_a_closed_window_holds_completion_until_it_opens(client: AsyncClient, db, market):
    from app.deals.models import Deal, DealStatus

    w = await _window(db, country="England", opens_in_days=50)
    deal_id = await _confirmed_deal(client, db, market)

    notice = (await client.get(f"/deals/{deal_id}/real-world", headers=_auth_headers(market["buyer"]))).json()
    assert notice["window"].startswith("The transfer window in England is closed.")
    assert "the January 2027 window opens on" in notice["window"]
    assert notice["window_opens_at"][:10] == w.opens_at.date().isoformat()

    held = await client.post(f"/deals/{deal_id}/advance", headers=_auth_headers(market["buyer"]))
    assert held.status_code in (400, 409) and "transfer window in England is closed" in held.text

    # Once it opens, the deal completes.
    w.opens_at = datetime.now(timezone.utc) - timedelta(hours=1)
    await db.commit()
    done = await client.post(f"/deals/{deal_id}/advance", headers=_auth_headers(market["buyer"]))
    assert done.status_code == 200, done.text
    db.expire_all()
    assert (await db.get(Deal, uuid.UUID(deal_id))).status == DealStatus.COMPLETED


@pytest.mark.asyncio
async def test_another_countrys_window_doesnt_hold_an_english_deal(client: AsyncClient, db, market):
    await _window(db, country="Spain", opens_in_days=50)
    deal_id = await _confirmed_deal(client, db, market)
    notice = (await client.get(f"/deals/{deal_id}/real-world", headers=_auth_headers(market["buyer"]))).json()
    assert notice["window"] is None
    assert (await client.post(f"/deals/{deal_id}/advance", headers=_auth_headers(market["buyer"]))).status_code == 200


@pytest.mark.asyncio
async def test_a_window_with_no_country_covers_clubs_whose_country_has_none(client: AsyncClient, db, market):
    from app.transfer_window import service

    await _window(db, opens_in_days=50, name="Global")
    assert not await service.registration_open(db, "England")
    # England's own windows take over from the global ones.
    await _window(db, country="England", opens_in_days=-1, name="England now")
    assert await service.registration_open(db, "england")  # matched regardless of case
    assert not await service.registration_open(db, "Spain")
    deal_id = await _confirmed_deal(client, db, market)
    assert (await client.post(f"/deals/{deal_id}/advance", headers=_auth_headers(market["buyer"]))).status_code == 200


@pytest.mark.asyncio
async def test_free_agents_and_pre_contracts_dont_wait_for_a_window(db):
    from app.deals.models import Deal, DealType
    from app.transfer_window import service

    await _window(db, opens_in_days=50)
    seller = uuid.uuid4()
    assert service.waits_for_window(Deal(seller_club_id=seller, deal_type=DealType.PERMANENT))
    assert service.waits_for_window(Deal(seller_club_id=seller, deal_type=DealType.LOAN))
    assert not service.waits_for_window(Deal(seller_club_id=None, deal_type=DealType.FREE_TRANSFER))
    assert not service.waits_for_window(Deal(seller_club_id=seller, deal_type=DealType.PRE_CONTRACT))
    assert await service.completion_hold(db, Deal(seller_club_id=None, deal_type=DealType.FREE_TRANSFER)) is None


@pytest.mark.asyncio
async def test_no_windows_means_an_open_market(client: AsyncClient, db, market):
    deal_id = await _confirmed_deal(client, db, market)
    assert (await client.get(f"/deals/{deal_id}/real-world", headers=_auth_headers(market["buyer"]))).json()["window"] is None
    assert (await client.post(f"/deals/{deal_id}/advance", headers=_auth_headers(market["buyer"]))).status_code == 200


# ── While it waits ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_waiting_for_the_window_isnt_overdue(client: AsyncClient, db, market):
    from app.deals.models import Deal
    from app.deals.service import check_deal_sla_breaches

    w = await _window(db, country="England", opens_in_days=50)
    deal_id = await _confirmed_deal(client, db, market)
    deal = await db.get(Deal, uuid.UUID(deal_id))
    deal.sla_deadline = datetime.now(timezone.utc) - timedelta(days=1)
    await db.commit()

    assert await check_deal_sla_breaches(db) == 0
    await db.commit()
    deal = await db.get(Deal, uuid.UUID(deal_id))
    assert deal.sla_escalated_at is None
    # The clock restarts when the window opens.
    deadline = deal.sla_deadline if deal.sla_deadline.tzinfo else deal.sla_deadline.replace(tzinfo=timezone.utc)
    opens = w.opens_at if w.opens_at.tzinfo else w.opens_at.replace(tzinfo=timezone.utc)
    assert abs((deadline - (opens + timedelta(days=14))).total_seconds()) < 60


@pytest.mark.asyncio
async def test_both_clubs_hear_once_when_the_window_opens(client: AsyncClient, db, market):
    from app.notifications.models import Notification
    from app.transfer_window.service import notify_opened_windows

    w = await _window(db, country="England", opens_in_days=50)
    deal_id = await _confirmed_deal(client, db, market)
    assert await notify_opened_windows(db) == 0

    w.opens_at = datetime.now(timezone.utc) - timedelta(minutes=5)
    await db.commit()
    assert await notify_opened_windows(db) == 1
    await db.commit()
    assert await notify_opened_windows(db) == 0  # only once
    told = (await db.execute(select(Notification).where(Notification.link == f"/deals/{deal_id}",
                                                         Notification.message.contains("window is open")))).scalars().all()
    assert {n.recipient_user_id for n in told}  # both clubs' members
    assert len({n.related_player_id for n in told}) == 1


# ── What clubs and admins see ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_status_follows_the_signed_in_clubs_country(client: AsyncClient, db, market):
    await _window(db, country="Spain", opens_in_days=-1, name="Spain now")
    await _window(db, country="England", opens_in_days=50, name="England later")
    mine = (await client.get("/transfers/window/status", headers=_auth_headers(market["buyer"]))).json()
    assert mine["country"] == "England" and mine["enforced"] and not mine["is_open"]
    assert mine["next_window"]["name"] == "England later"
    spain = (await client.get("/transfers/window/status", params={"country": "Spain"})).json()
    assert spain["is_open"] and spain["current_window"]["name"] == "Spain now"
    anyone = (await client.get("/transfers/window/status")).json()
    assert anyone["enforced"] is False  # no window covers every club


@pytest.mark.asyncio
async def test_lite_home_offers_buying_while_the_window_is_closed(client: AsyncClient, db, market):
    await _window(db, country="England", opens_in_days=50)
    home = (await client.get("/lite/home", headers=_auth_headers(market["buyer"]))).json()
    assert home["window"]["state"] == "closed"
    assert [t["key"] for t in home["tiles"]] == ["buy", "sell", "offers", "ask"]


@pytest.mark.asyncio
async def test_admin_records_the_country_and_source_and_sees_gaps(client: AsyncClient, db, market):
    from app.auth.models import User

    admin_tokens = await _register(client, "admin_tw@transferx-example.com", club_name="Admin Club")
    user = (await db.execute(select(User).where(User.email == "admin_tw@transferx-example.com"))).scalar_one()
    user.is_superuser = True
    await db.commit()
    h = _auth_headers(admin_tokens)

    gaps = {c["country"]: c for c in (await client.get("/transfers/window/coverage", headers=h)).json()}
    assert gaps["England"]["missing"] is True and gaps["England"]["next_window"] is None

    bad = await client.post("/transfers/window", headers=h, json={
        "name": "January 2027", "country": "England", "opens_at": "2027-01-01T00:00:00Z",
        "closes_at": "2027-02-02T23:00:00Z", "source_url": "fifa calendar"})
    assert bad.status_code == 422

    opens = (datetime.now(timezone.utc) + timedelta(days=60)).replace(microsecond=0)
    created = await client.post("/transfers/window", headers=h, json={
        "name": "January 2027", "country": "England", "opens_at": opens.isoformat(),
        "closes_at": (opens + timedelta(days=32)).isoformat(),
        "source_url": "https://inside.fifa.com/associations/ENG/snapshot", "checked_on": "2026-11-07"})
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["country"] == "England" and body["checked_on"] == "2026-11-07"
    assert body["source_url"].startswith("https://inside.fifa.com")

    gaps = {c["country"]: c for c in (await client.get("/transfers/window/coverage", headers=h)).json()}
    assert gaps["England"]["missing"] is False and gaps["England"]["own_windows"] is True
    assert gaps["England"]["next_window"]["name"] == "January 2027"
    # Only staff see coverage.
    assert (await client.get("/transfers/window/coverage", headers=_auth_headers(market["buyer"]))).status_code == 403
