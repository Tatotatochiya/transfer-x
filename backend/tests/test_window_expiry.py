"""Offers and deals run out at the buying club's window close by default
(product ADR 0014). A deal that hasn't completed by then collapses, with its
budget released; both clubs are warned two days before."""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from tests.conftest import _auth_headers, _register
from tests.test_offers import _create_player, _get_seller_club_id, _give_budget, _make_offer

pytestmark = pytest.mark.asyncio


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


async def _window(db, *, opens: timedelta, closes: timedelta, country: str | None = None):
    from app.transfer_window.models import TransferWindow

    now = _now()
    w = TransferWindow(name="Test", country=country, opens_at=now + opens, closes_at=now + closes)
    db.add(w)
    await db.commit()
    return _aware(w.closes_at)


@pytest.fixture
async def clubs(client: AsyncClient, db):
    seller = await _register(client, "win_seller@test.com", club_name="Seller FC")
    buyer = await _register(client, "win_buyer@test.com", club_name="Buyer FC")
    await _give_budget(db)
    player = await _create_player(client, _auth_headers(seller), name="Window Man")
    return {"seller": seller, "buyer": buyer, "player": player["id"],
            "seller_id": await _get_seller_club_id(client, _auth_headers(seller))}


def _close_to(value: str, expected: datetime) -> bool:
    return abs(_aware(datetime.fromisoformat(value)) - expected) < timedelta(seconds=2)


async def test_an_offer_lasts_until_the_open_window_closes(client: AsyncClient, db, clubs):
    closes = await _window(db, opens=-timedelta(days=10), closes=timedelta(days=20))
    offer = await _make_offer(client, _auth_headers(clubs["buyer"]), clubs["player"], clubs["seller_id"])
    assert _close_to(offer["expires_at"], closes)


async def test_between_windows_an_offer_lasts_until_the_next_one_closes(client: AsyncClient, db, clubs):
    await _window(db, opens=-timedelta(days=90), closes=-timedelta(days=60))
    closes = await _window(db, opens=timedelta(days=30), closes=timedelta(days=60))
    offer = await _make_offer(client, _auth_headers(clubs["buyer"]), clubs["player"], clubs["seller_id"])
    assert _close_to(offer["expires_at"], closes)


async def test_the_buyers_own_country_decides(client: AsyncClient, db, clubs):
    from app.clubs.models import Club

    buyer = (await db.execute(select(Club).where(Club.name == "Buyer FC"))).scalar_one()
    buyer.country = "Spain"
    await db.commit()
    await _window(db, opens=-timedelta(days=10), closes=timedelta(days=5), country="England")
    spain = await _window(db, opens=-timedelta(days=10), closes=timedelta(days=12), country="Spain")
    offer = await _make_offer(client, _auth_headers(clubs["buyer"]), clubs["player"], clubs["seller_id"])
    assert _close_to(offer["expires_at"], spain)


async def test_with_no_windows_an_offer_lasts_a_week_and_a_chosen_date_is_kept(client: AsyncClient, db, clubs):
    offer = await _make_offer(client, _auth_headers(clubs["buyer"]), clubs["player"], clubs["seller_id"])
    assert abs(_aware(datetime.fromisoformat(offer["expires_at"])) - (_now() + timedelta(days=7))) < timedelta(minutes=1)

    await _window(db, opens=-timedelta(days=10), closes=timedelta(days=20))
    chosen = (_now() + timedelta(days=2)).replace(microsecond=0)
    r = await client.post(f"/offers/{offer['id']}/withdraw", headers=_auth_headers(clubs["buyer"]))
    assert r.status_code == 200, r.text
    r = await client.post("/offers", json={
        "player_id": clubs["player"], "to_club_id": clubs["seller_id"], "fee_amount": 5_000_000,
        "expires_at": chosen.isoformat(),
    }, headers=_auth_headers(clubs["buyer"]))
    assert r.status_code == 201, r.text
    assert _close_to(r.json()["expires_at"], chosen)


async def _agreed_deal(client, clubs) -> dict:
    offer = await _make_offer(client, _auth_headers(clubs["buyer"]), clubs["player"], clubs["seller_id"])
    r = await client.post(f"/offers/{offer['id']}/accept", headers=_auth_headers(clubs["seller"]))
    assert r.status_code == 200, r.text
    deal_id = r.json()["id"]
    r = await client.get(f"/deals/{deal_id}", headers=_auth_headers(clubs["buyer"]))
    assert r.status_code == 200, r.text
    return r.json()


async def _deal_row(db, deal_id: str):
    from app.deals.models import Deal

    db.expire_all()
    return (await db.execute(select(Deal).where(Deal.id == uuid.UUID(deal_id)))).scalar_one()


async def _types(db, email: str) -> list[str]:
    from app.auth.models import User
    from app.notifications.models import Notification

    db.expire_all()
    uid = (await db.execute(select(User.id).where(User.email == email))).scalar_one()
    rows = (await db.execute(select(Notification.type).where(Notification.recipient_user_id == uid))).scalars()
    return [t.value for t in rows]


async def test_a_deal_collapses_when_the_window_closes(client: AsyncClient, db, clubs):
    from app.clubs.models import Club, ClubFinance
    from app.deals.models import DealStatus
    from app.deals.service import WINDOW_CLOSED_REASON, expire_deals

    closes = await _window(db, opens=-timedelta(days=10), closes=timedelta(days=20))
    deal = await _agreed_deal(client, clubs)
    assert _close_to(deal["expires_at"], closes)

    # Twenty days on: the window has closed with the deal not completed.
    row = await _deal_row(db, deal["id"])
    row.expires_at = _now() - timedelta(minutes=1)
    await db.commit()
    assert await expire_deals(db) == 1
    await db.commit()

    row = await _deal_row(db, deal["id"])
    assert row.status == DealStatus.COLLAPSED
    buyer = (await db.execute(select(Club).where(Club.name == "Buyer FC"))).scalar_one()
    finance = (await db.execute(select(ClubFinance).where(ClubFinance.club_id == buyer.id))).scalar_one()
    assert finance.transfer_committed == 0
    page = (await client.get(f"/deals/{deal['id']}", headers=_auth_headers(clubs["seller"]))).json()
    assert page["collapse_reason"] == WINDOW_CLOSED_REASON
    for email in ("win_buyer@test.com", "win_seller@test.com"):
        assert "DEAL_COLLAPSED" in await _types(db, email)
    assert await expire_deals(db) == 0  # already collapsed: nothing twice


async def test_both_clubs_are_warned_once_two_days_before(client: AsyncClient, db, clubs):
    from app.deals.service import expire_deals

    await _window(db, opens=-timedelta(days=10), closes=timedelta(days=20))
    deal = await _agreed_deal(client, clubs)
    row = await _deal_row(db, deal["id"])
    row.expires_at = _now() + timedelta(hours=30)
    await db.commit()

    assert await expire_deals(db) == 0
    await expire_deals(db)
    await db.commit()
    for email in ("win_buyer@test.com", "win_seller@test.com"):
        assert (await _types(db, email)).count("DEAL_EXPIRING") == 1


async def test_an_open_deal_from_before_windows_were_set_gets_its_date(client: AsyncClient, db, clubs):
    from app.deals.service import expire_deals

    deal = await _agreed_deal(client, clubs)  # no windows yet: no date
    assert deal["expires_at"] is None
    closes = await _window(db, opens=-timedelta(days=10), closes=timedelta(days=20))
    await expire_deals(db)
    await db.commit()
    assert abs(_aware((await _deal_row(db, deal["id"])).expires_at) - closes) < timedelta(seconds=2)
