"""Mobile notifications, phase 4: the 30-minute email fallback, the morning
summary push, and the decision sheet's facts on the Lite offer card."""
import asyncio
import uuid
from datetime import datetime, time, timedelta, timezone
from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select

from app.config import settings
from app.lite.models import UserPreference
from app.notifications import push
from app.notifications.models import (
    Notification, NotificationPreference, NotificationType, PushDelivery, PushPlatform, PushSubscription,
)
from app.notifications.service import create_notification
from tests.conftest import _auth_headers, _register
from tests.test_deals import _create_player_for_seller, _get_club_id, _give_budget

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def _vapid(monkeypatch):
    monkeypatch.setattr(settings, "vapid_public_key", "BKey")
    monkeypatch.setattr(settings, "vapid_private_key", "private")
    monkeypatch.setattr(settings, "vapid_subject", "mailto:t@test")

    async def no_send(nid):
        return None

    monkeypatch.setattr(push, "send_for_notification", no_send)


@pytest.fixture
def emails(monkeypatch):
    """Records every notification email instead of sending it."""
    sent: list = []

    async def record(user_id, type_, message, link):
        sent.append((user_id, type_, message))

    import app.notifications.email as email_module
    monkeypatch.setattr(email_module, "maybe_send_notification_email", record)
    return sent


@pytest.fixture
def pushes(monkeypatch):
    calls: list = []

    async def fake_post(sub, payload, headers):
        calls.append(payload)
        return 201

    monkeypatch.setattr(push, "_post", fake_post)
    return calls


@pytest_asyncio.fixture
async def seller(client: AsyncClient, db) -> dict:
    tokens = await _register(client, "p4_seller@test.com", club_name="Phase Four Sellers")
    me = (await client.get("/auth/me", headers=_auth_headers(tokens))).json()
    return {"tokens": tokens, "id": uuid.UUID(me["id"]), "headers": _auth_headers(tokens)}


async def _device(db, user_id):
    db.add(PushSubscription(user_id=user_id, endpoint=f"https://push.example/{user_id}", p256dh="p", auth="a",
                            platform=PushPlatform.ANDROID))
    await db.flush()


async def _settle():
    await asyncio.sleep(0)  # let fire-and-forget email tasks run


# ── Email fallback ────────────────────────────────────────────────────────────


async def test_with_a_phone_the_your_move_email_waits_for_the_fallback(db, seller, emails):
    await _device(db, seller["id"])
    n = await create_notification(db, recipient_user_id=seller["id"], type=NotificationType.OFFER_RECEIVED, message="Offer")
    await _settle()
    assert emails == []  # not now
    assert n.email_due_at is not None
    assert timedelta(minutes=29) < push._aware(n.email_due_at) - datetime.now(timezone.utc) <= timedelta(minutes=30)


async def test_without_a_phone_or_with_push_off_the_email_goes_now(db, seller, emails):
    n = await create_notification(db, recipient_user_id=seller["id"], type=NotificationType.OFFER_RECEIVED, message="Offer")
    await _settle()
    assert len(emails) == 1 and n.email_due_at is None

    await _device(db, seller["id"])
    db.add(NotificationPreference(user_id=seller["id"], type=NotificationType.OFFER_COUNTERED, push_enabled=False))
    await db.flush()
    n2 = await create_notification(db, recipient_user_id=seller["id"], type=NotificationType.OFFER_COUNTERED, message="Counter")
    await _settle()
    assert len(emails) == 2 and n2.email_due_at is None
    # A heads-up type isn't "your move": its email (if any) is never deferred.
    assert not await push.will_push(db, seller["id"], NotificationType.OFFER_EXPIRING)


async def test_the_fallback_emails_only_what_is_still_unread(db, seller, emails):
    await _device(db, seller["id"])
    unread = await create_notification(db, recipient_user_id=seller["id"], type=NotificationType.OFFER_RECEIVED, message="Unread")
    read = await create_notification(db, recipient_user_id=seller["id"], type=NotificationType.APPROVAL_REQUESTED, message="Read")
    read.is_read = True
    await db.flush()
    await _settle()
    assert emails == []

    assert await push.send_email_fallbacks(db, datetime.now(timezone.utc) + timedelta(minutes=10)) == 0  # not yet
    assert await push.send_email_fallbacks(db, datetime.now(timezone.utc) + timedelta(minutes=31)) == 1
    assert [m for (_u, _t, m) in emails] == ["Unread"]
    assert unread.emailed_at is not None and read.emailed_at is not None
    assert await push.send_email_fallbacks(db, datetime.now(timezone.utc) + timedelta(minutes=40)) == 0  # once only


# ── Morning summary ───────────────────────────────────────────────────────────


async def _incoming_offer(client, db, seller) -> dict:
    buyer = await _register(client, "p4_buyer@test.com", club_name="Phase Four Buyers")
    await _give_budget(db)
    player = await _create_player_for_seller(client, seller["headers"])
    resp = await client.post("/offers", json={"player_id": player["id"], "fee_amount": 5_000_000,
                                               "to_club_id": await _get_club_id(client, seller["headers"])},
                             headers=_auth_headers(buyer))
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_one_morning_summary_a_day_when_something_is_waiting(client: AsyncClient, db, seller, pushes, emails):
    await _device(db, seller["id"])
    db.add(UserPreference(user_id=seller["id"], timezone="Europe/London", summary_local_time=time(8, 0)))
    await db.commit()

    # 06:00 UTC in July is 07:00 London: before the summary time, and nothing is waiting yet anyway.
    early = datetime(2026, 7, 1, 6, 0, tzinfo=timezone.utc)
    assert await push.send_morning_summaries(db, early) == 0

    await _incoming_offer(client, db, seller)
    assert await push.send_morning_summaries(db, early) == 0  # still before 08:00
    morning = datetime(2026, 7, 1, 7, 30, tzinfo=timezone.utc)  # 08:30 London
    assert await push.send_morning_summaries(db, morning) == 1
    note = pushes[-1]["notification"]
    assert note["title"] == "1 thing waiting on you"
    assert note["body"].startswith("1 offer · first deadline ")
    assert note["tag"] == "digest" and note["navigate"].endswith("/dashboard?from=push")
    assert await push.send_morning_summaries(db, morning + timedelta(hours=2)) == 0  # once a day
    assert (await db.execute(select(PushDelivery).where(PushDelivery.group_key == "digest"))).scalars().first()


async def test_the_summary_can_be_switched_off_two_ways(client: AsyncClient, db, seller, pushes, emails):
    await _device(db, seller["id"])
    await _incoming_offer(client, db, seller)
    morning = datetime(2026, 7, 1, 9, 0, tzinfo=timezone.utc)
    db.add(UserPreference(user_id=seller["id"], push_summary=False))
    await db.commit()
    assert await push.send_morning_summaries(db, morning) == 0

    prefs = await db.get(UserPreference, seller["id"])
    prefs.push_summary = True
    db.add(NotificationPreference(user_id=seller["id"], type=NotificationType.DAILY_DIGEST, enabled=False))
    await db.commit()
    assert await push.send_morning_summaries(db, morning) == 0  # the Daily digest preference stops it too


def test_summary_wording():
    from types import SimpleNamespace
    from zoneinfo import ZoneInfo

    now = datetime(2026, 10, 2, 9, 0, tzinfo=timezone.utc)
    items = [SimpleNamespace(kind="offer", deadline=now + timedelta(hours=9)),
             SimpleNamespace(kind="offer", deadline=None),
             SimpleNamespace(kind="approval", deadline=now + timedelta(days=1))]
    title, body = push._summary_text(items, ZoneInfo("Europe/London"), now)
    assert title == "3 things waiting on you"
    assert body == "2 offers and 1 approval · first deadline today 19:00"


# ── The decision sheet's facts ────────────────────────────────────────────────


async def test_the_sellers_card_carries_its_valuation_and_asks_for_it(client: AsyncClient, db, seller):
    from app.players.models import Contract

    offer = await _incoming_offer(client, db, seller)
    contract = (await db.execute(select(Contract).where(Contract.player_id == uuid.UUID(offer["player_id"])))).scalars().first()
    if contract is None:
        contract = Contract(player_id=uuid.UUID(offer["player_id"]), club_id=uuid.UUID(await _get_club_id(client, seller["headers"])),
                            is_active=True)
        db.add(contract)
    contract.club_valuation = Decimal("9000000")
    await db.commit()
    card = (await client.get(f"/lite/offers/{offer['id']}", headers=seller["headers"])).json()
    assert card["your_valuation"] == 9_000_000
    assert card["counter_suggestion"] == 9_000_000
    assert card["expires_at"]
    # The buyer never sees the seller's valuation.
    buyer_login = await client.post("/auth/login", json={"email": "p4_buyer@test.com", "password": "password123"})
    buyer_card = (await client.get(f"/lite/offers/{offer['id']}", headers=_auth_headers(buyer_login.json()))).json()
    assert buyer_card["your_valuation"] is None
