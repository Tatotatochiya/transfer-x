"""Mobile notifications, phase 1 (docs/feature_spec/mobile-notifications):
the tier map, the push decision (tiers, settings, quiet hours, repeats),
the payload, device handling, the endpoints, and the hourly reminders
telling each person once."""
import uuid
from datetime import datetime, time, timedelta, timezone
from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import func, select

from app.config import settings
from app.lite.models import PushMode, UserPreference
from app.notifications import push
from app.notifications.models import (
    Notification,
    NotificationPreference,
    NotificationType,
    PushDelivery,
    PushDeliveryStatus,
    PushPlatform,
    PushSubscription,
)
from app.notifications.service import create_notification
from app.notifications.tiers import TIERS, Tier
from tests.conftest import _auth_headers, _register

# 12:00 UTC on a summer day is 13:00 in London: outside the default quiet hours.
NOON = datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc)
# 23:00 UTC is midnight in London: inside them (22:00 to 07:00, so they end at 06:00 UTC).
NIGHT = datetime(2026, 7, 1, 23, 0, tzinfo=timezone.utc)
QUIET_END = datetime(2026, 7, 2, 6, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def _vapid(monkeypatch):
    monkeypatch.setattr(settings, "vapid_public_key", "BPublicKeyForTests")
    monkeypatch.setattr(settings, "vapid_private_key", "private-key-for-tests")
    monkeypatch.setattr(settings, "vapid_subject", "mailto:test@transferx.test")

    # A commit would otherwise start a real send, in its own session on the
    # real database. Tests of the send itself call push.deliver directly.
    async def no_send(nid):
        return None

    monkeypatch.setattr(push, "send_for_notification", no_send)


@pytest.fixture
def sent(monkeypatch):
    """Replaces the HTTP send: records each (endpoint, payload, headers) and
    answers with the status set in `sent.status` (201 by default)."""
    calls: list = []

    async def fake_post(sub, payload, headers):
        calls.append((sub.endpoint, payload, headers))
        return fake_post.status

    fake_post.status = 201
    calls_holder = type("Sent", (), {})()
    calls_holder.calls = calls
    calls_holder.set_status = lambda s: setattr(fake_post, "status", s)
    monkeypatch.setattr(push, "_post", fake_post)

    async def no_badge(db, user_id):
        return 3

    monkeypatch.setattr(push, "_badge_count", no_badge)
    return calls_holder


@pytest_asyncio.fixture
async def user(client: AsyncClient) -> dict:
    tokens = await _register(client, "push_user@test.com", club_name="Push FC")
    me = (await client.get("/auth/me", headers=_auth_headers(tokens))).json()
    return {"tokens": tokens, "id": uuid.UUID(me["id"]), "headers": _auth_headers(tokens)}


async def _device(db, user_id, endpoint="https://push.example/device-1") -> PushSubscription:
    sub = PushSubscription(user_id=user_id, endpoint=endpoint, p256dh="p", auth="a", platform=PushPlatform.ANDROID)
    db.add(sub)
    await db.flush()
    return sub


async def _notification(db, user_id, type_=NotificationType.OFFER_RECEIVED, **kw) -> Notification:
    n = Notification(
        recipient_user_id=user_id, type=type_, message=kw.pop("message", "You received an offer"),
        link=kw.pop("link", "/offers/abc"), is_read=False, **kw,
    )
    db.add(n)
    await db.flush()
    return n


# ── Tier map ──────────────────────────────────────────────────────────────────


def test_every_notification_type_has_a_tier():
    missing = set(NotificationType) - set(TIERS)
    assert not missing, f"Add these to app/notifications/tiers.py: {sorted(m.value for m in missing)}"


def test_tiers_match_the_spec_examples():
    assert TIERS[NotificationType.OFFER_RECEIVED] is Tier.YOUR_MOVE
    assert TIERS[NotificationType.OUTBID] is Tier.HEADS_UP
    assert TIERS[NotificationType.DEAL_COMPLETED] is Tier.FYI


# ── Quiet hours ───────────────────────────────────────────────────────────────


def test_quiet_hours_wrap_midnight_in_the_users_timezone():
    prefs = UserPreference(quiet_hours_enabled=True, quiet_start=time(22, 0), quiet_end=time(7, 0), timezone="Europe/London")
    assert push.quiet_until(prefs, NOON) is None
    assert push.quiet_until(prefs, NIGHT) == QUIET_END
    # 05:30 London (04:30 UTC) is still inside, ending the same morning.
    early = datetime(2026, 7, 2, 4, 30, tzinfo=timezone.utc)
    assert push.quiet_until(prefs, early) == QUIET_END
    # The same instant is 13:30 in Singapore: outside.
    prefs.timezone = "Asia/Singapore"
    assert push.quiet_until(prefs, NOON) is None


def test_quiet_hours_off_or_empty_window_never_hold():
    off = UserPreference(quiet_hours_enabled=False, quiet_start=time(22, 0), quiet_end=time(7, 0), timezone="Europe/London")
    assert push.quiet_until(off, NIGHT) is None
    same = UserPreference(quiet_hours_enabled=True, quiet_start=time(7, 0), quiet_end=time(7, 0), timezone="Europe/London")
    assert push.quiet_until(same, NIGHT) is None


def test_no_preferences_row_uses_the_defaults():
    assert push.quiet_until(None, NIGHT) == QUIET_END
    assert push.quiet_until(None, NOON) is None


# ── The decision ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_your_move_outside_quiet_hours_is_sent_with_sound(db, user, sent):
    await _device(db, user["id"])
    n = await _notification(db, user["id"], title="Offer for Marcus Webb: £18m", body="Ashfield United",
                            group_key="offer:abc")
    d = await push.deliver(db, n, NOON)
    assert d.status is PushDeliveryStatus.SENT and d.sent_at == NOON
    (_endpoint, payload, headers), = sent.calls
    assert payload["notification"]["silent"] is False
    assert headers["Urgency"] == "high"
    assert headers["Topic"] == push.topic_for("offer:abc")


@pytest.mark.asyncio
async def test_heads_up_is_silent_and_normal_urgency(db, user, sent):
    await _device(db, user["id"])
    n = await _notification(db, user["id"], type_=NotificationType.OUTBID)
    await push.deliver(db, n, NOON)
    (_e, payload, headers), = sent.calls
    assert payload["notification"]["silent"] is True
    assert headers["Urgency"] == "normal"


@pytest.mark.asyncio
async def test_fyi_no_device_or_switched_off_is_not_pushed(db, user, sent):
    n = await _notification(db, user["id"])
    assert await push.deliver(db, n, NOON) is None  # no device yet

    await _device(db, user["id"])
    fyi = await _notification(db, user["id"], type_=NotificationType.DEAL_COMPLETED)
    assert await push.deliver(db, fyi, NOON) is None

    db.add(NotificationPreference(user_id=user["id"], type=NotificationType.OFFER_RECEIVED, push_enabled=False))
    await db.flush()
    assert await push.deliver(db, n, NOON) is None

    db.add(UserPreference(user_id=user["id"], push_heads_up=PushMode.OFF))
    await db.flush()
    outbid = await _notification(db, user["id"], type_=NotificationType.OUTBID)
    assert await push.deliver(db, outbid, NOON) is None
    assert sent.calls == []


@pytest.mark.asyncio
async def test_quiet_hours_hold_then_release(db, user, sent):
    await _device(db, user["id"])
    n = await _notification(db, user["id"], type_=NotificationType.OUTBID)
    d = await push.deliver(db, n, NIGHT)
    assert d.status is PushDeliveryStatus.HELD
    assert push._aware(d.send_after) == QUIET_END
    assert sent.calls == []

    assert await push.release_held_pushes(db, QUIET_END - timedelta(minutes=1)) == 0
    assert await push.release_held_pushes(db, QUIET_END) == 1
    assert d.status is PushDeliveryStatus.SENT
    assert len(sent.calls) == 1


@pytest.mark.asyncio
async def test_a_held_push_read_in_the_meantime_is_skipped(db, user, sent):
    await _device(db, user["id"])
    n = await _notification(db, user["id"], type_=NotificationType.OUTBID)
    d = await push.deliver(db, n, NIGHT)
    n.is_read = True
    await push.release_held_pushes(db, QUIET_END)
    assert d.status is PushDeliveryStatus.SKIPPED
    assert sent.calls == []


@pytest.mark.asyncio
async def test_your_move_breaks_through_when_the_deadline_comes_before_morning(db, user, sent):
    """Review decision 2: an offer that expires at 03:00 must not wait until
    07:00. The spec's "under 2 hours" rule would have held it."""
    await _device(db, user["id"])
    expires_at_3am = datetime(2026, 7, 2, 2, 0, tzinfo=timezone.utc)  # 03:00 London, 3h after NIGHT
    n = await _notification(db, user["id"], deadline_at=expires_at_3am)
    assert (await push.deliver(db, n, NIGHT)).status is PushDeliveryStatus.SENT

    # Within the hour after quiet hours end: still let through.
    soon_after = await _notification(db, user["id"], deadline_at=QUIET_END + timedelta(minutes=45))
    assert (await push.deliver(db, soon_after, NIGHT)).status is PushDeliveryStatus.SENT

    # A deadline later in the day waits for the morning.
    later = await _notification(db, user["id"], deadline_at=QUIET_END + timedelta(hours=5))
    assert (await push.deliver(db, later, NIGHT)).status is PushDeliveryStatus.HELD

    # Only "your move" breaks through: a heads-up with a near deadline waits.
    heads_up = await _notification(db, user["id"], type_=NotificationType.AUCTION_ENDING, deadline_at=expires_at_3am)
    assert (await push.deliver(db, heads_up, NIGHT)).status is PushDeliveryStatus.HELD


@pytest.mark.asyncio
async def test_a_reminder_is_not_pushed_twice_but_news_is(db, user, sent):
    await _device(db, user["id"])
    first = await _notification(db, user["id"], type_=NotificationType.OFFER_EXPIRING, group_key="offer:abc")
    second = await _notification(db, user["id"], type_=NotificationType.OFFER_EXPIRING, group_key="offer:abc")
    assert (await push.deliver(db, first, NOON)).status is PushDeliveryStatus.SENT
    assert (await push.deliver(db, second, NOON + timedelta(hours=1))).status is PushDeliveryStatus.SKIPPED_DUPLICATE

    # A second counter-offer on the same offer is news, not a repeat.
    c1 = await _notification(db, user["id"], type_=NotificationType.OFFER_COUNTERED, group_key="offer:abc")
    c2 = await _notification(db, user["id"], type_=NotificationType.OFFER_COUNTERED, group_key="offer:abc")
    assert (await push.deliver(db, c1, NOON)).status is PushDeliveryStatus.SENT
    assert (await push.deliver(db, c2, NOON)).status is PushDeliveryStatus.SENT


# ── Payload ───────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_payload_has_the_declarative_and_classic_shape(db, user, sent):
    await _device(db, user["id"])
    n = await _notification(
        db, user["id"], title="Offer for Marcus Webb: £18m",
        body="Ashfield United · your valuation £21m · reply by Fri 18:00", group_key="offer:abc",
    )
    n.actions_json = [
        {"action": "counter", "title": "Ask for £21m", "url": "/offers/abc?action=counter&amount=21000000"},
        {"action": "open", "title": "Open", "url": "/offers/abc"},
        {"action": "extra", "title": "Never shown", "url": "/"},
    ]
    await push.deliver(db, n, NOON)
    (_e, payload, _h), = sent.calls
    assert payload["web_push"] == 8030
    note = payload["notification"]
    assert note["title"] == "Offer for Marcus Webb: £18m"
    assert note["body"].startswith("Ashfield United")
    assert note["tag"] == "offer:abc"
    assert note["lang"] == "en-GB"
    assert note["app_badge"] == "3"
    from urllib.parse import parse_qs, urlparse

    nav = urlparse(note["navigate"])
    assert f"{nav.scheme}://{nav.netloc}{nav.path}" == f"{settings.frontend_base_url}/offers/abc"
    q = parse_qs(nav.query)
    assert q["from"] == ["push"] and q["nid"] == [str(n.id)]
    # iOS opens declarative pushes without the service worker: the page reports the tap.
    assert push.read_open_token(q["ot"][0], n.id) == user["id"]
    assert [a["action"] for a in note["actions"]] == ["counter", "open"]
    assert "action=counter&amount=21000000&from=push&nid=" in note["actions"][0]["navigate"]
    assert note["data"]["tier"] == "YOUR_MOVE" and note["data"]["renotify"] is True
    assert push.read_open_token(note["data"]["open_token"], n.id) == user["id"]


@pytest.mark.asyncio
async def test_hide_amounts_shows_only_what_happened(db, user, sent):
    """Review decision 1: no figures, club names or message text on the lock screen."""
    await _device(db, user["id"])
    db.add(UserPreference(user_id=user["id"], push_hide_amounts=True))
    await db.flush()
    n = await _notification(db, user["id"], title="Offer for Marcus Webb: £18m", body="Ashfield United · £21m")
    n.actions_json = [{"action": "counter", "title": "Ask for £21m", "url": "/offers/abc"}]
    await push.deliver(db, n, NOON)
    (_e, payload, _h), = sent.calls
    note = payload["notification"]
    assert note["title"] == "New offer received"
    assert note["body"] == "Open TransferX to see the details."
    assert "actions" not in note
    assert "£" not in str({k: v for k, v in note.items() if k != "data"})


@pytest.mark.asyncio
async def test_title_falls_back_to_the_message(db, user, sent):
    await _device(db, user["id"])
    n = await _notification(db, user["id"], message="New message in your negotiation",
                            type_=NotificationType.NEGOTIATION_MESSAGE, link="/deals/d1")
    await push.deliver(db, n, NOON)
    note = sent.calls[0][1]["notification"]
    assert note["title"] == "New message in your negotiation"
    assert "body" not in note
    assert note["tag"] == f"n:{n.id}"


def test_open_token_is_for_one_notification_only():
    uid, nid = uuid.uuid4(), uuid.uuid4()
    token = push.open_token(uid, nid)
    assert push.read_open_token(token, nid) == uid
    assert push.read_open_token(token, uuid.uuid4()) is None
    assert push.read_open_token("not-a-token", nid) is None


# ── Devices ───────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_a_410_deletes_the_subscription(db, user, sent):
    sub = await _device(db, user["id"])
    sent.set_status(410)
    n = await _notification(db, user["id"])
    d = await push.deliver(db, n, NOON)
    await db.flush()
    assert d.status is PushDeliveryStatus.FAILED
    assert await db.get(PushSubscription, sub.id) is None


@pytest.mark.asyncio
async def test_five_failures_in_a_row_delete_the_subscription(db, user, sent):
    sub = await _device(db, user["id"])
    sent.set_status(500)
    for i in range(4):
        await push.deliver(db, await _notification(db, user["id"]), NOON)
    assert sub.failure_count == 4
    await push.deliver(db, await _notification(db, user["id"]), NOON)
    await db.flush()
    assert await db.get(PushSubscription, sub.id) is None


# ── Sent only after commit ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_push_waits_for_commit_and_is_dropped_on_rollback(db, user, monkeypatch):
    started: list = []

    async def fake_send(nid):
        started.append(nid)

    monkeypatch.setattr(push, "send_for_notification", fake_send)
    n = await create_notification(db, recipient_user_id=user["id"], type=NotificationType.OFFER_RECEIVED, message="x")
    assert started == []
    await db.rollback()
    assert started == []

    n = await create_notification(db, recipient_user_id=user["id"], type=NotificationType.OFFER_RECEIVED, message="x")
    await db.commit()
    import asyncio
    await asyncio.sleep(0)
    assert started == [n.id]


@pytest.mark.asyncio
async def test_nothing_is_queued_without_vapid_keys(db, user, monkeypatch):
    monkeypatch.setattr(settings, "vapid_private_key", None)
    await create_notification(db, recipient_user_id=user["id"], type=NotificationType.OFFER_RECEIVED, message="x")
    assert push._PENDING not in db.sync_session.info
    await db.commit()


# ── Hourly reminders tell each person once ───────────────────────────────────


@pytest.mark.asyncio
async def test_once_skips_a_second_notification_about_the_same_subject(db, user):
    kw = dict(recipient_user_id=user["id"], type=NotificationType.OFFER_EXPIRING, message="Expiring",
              group_key="offer:abc", once=True)
    assert await create_notification(db, **kw) is not None
    assert await create_notification(db, **kw) is None
    assert await create_notification(db, **{**kw, "group_key": "offer:other"}) is not None


@pytest.mark.asyncio
async def test_the_hourly_job_reminds_about_an_expiring_offer_once(client: AsyncClient, db):
    from app.clubs.models import ClubFinance
    from app.notifications.service import notify_upcoming_events
    from app.offers.models import Offer

    seller = await _register(client, "push_seller@test.com", club_name="Push Sellers FC")
    buyer = await _register(client, "push_buyer@test.com", club_name="Push Buyers FC")
    for f in (await db.execute(select(ClubFinance))).scalars():
        f.transfer_budget_total = Decimal("50000000")
    await db.commit()
    player = (await client.post("/players", json={"name": "Expiring Man", "position": "MID"},
                                headers=_auth_headers(seller))).json()
    seller_club = (await client.get("/clubs/me", headers=_auth_headers(seller))).json()["id"]
    offer = (await client.post("/offers", json={"player_id": player["id"], "to_club_id": seller_club,
                                                "fee_amount": 5_000_000}, headers=_auth_headers(buyer))).json()
    row = await db.get(Offer, uuid.UUID(offer["id"]))
    row.expires_at = datetime.now(timezone.utc) + timedelta(hours=10)
    await db.commit()

    for _ in range(3):  # three hourly runs
        await notify_upcoming_events(db)
        await db.commit()
    count = (await db.execute(select(func.count()).select_from(Notification).where(
        Notification.type == NotificationType.OFFER_EXPIRING))).scalar_one()
    assert count == 1


# ── Endpoints ─────────────────────────────────────────────────────────────────


SUBSCRIBE = {
    "endpoint": "https://fcm.googleapis.com/fcm/send/abc",
    "keys": {"p256dh": "BKey", "auth": "auth-secret"},
    "platform": "ANDROID",
    "timezone": "Europe/Madrid",
}


@pytest.mark.asyncio
async def test_subscribe_list_and_remove_a_device(client: AsyncClient, db, user):
    h = {**user["headers"], "User-Agent": "Mozilla/5.0 (Linux; Android 14) Chrome/130.0 Mobile"}
    assert (await client.get("/notifications/push/public-key")).json() == {"key": "BPublicKeyForTests"}

    resp = await client.post("/notifications/push/subscriptions", json=SUBSCRIBE, headers=h)
    assert resp.status_code == 201, resp.text
    assert resp.json()["label"] == "Android · Chrome"
    # Subscribing again (same endpoint) updates rather than duplicates.
    await client.post("/notifications/push/subscriptions", json=SUBSCRIBE, headers=h)
    devices = (await client.get("/notifications/push/subscriptions", headers=h)).json()
    assert len(devices) == 1
    prefs = (await client.get("/users/me/preferences", headers=h)).json()
    assert prefs["timezone"] == "Europe/Madrid"

    resp = await client.request("DELETE", "/notifications/push/subscriptions",
                                json={"endpoint": SUBSCRIBE["endpoint"]}, headers=h)
    assert resp.status_code == 204
    assert (await client.get("/notifications/push/subscriptions", headers=h)).json() == []


@pytest.mark.asyncio
async def test_a_device_moves_to_whoever_subscribed_last(client: AsyncClient, db, user):
    other = await _register(client, "push_other@test.com", club_name="Other FC")
    await client.post("/notifications/push/subscriptions", json=SUBSCRIBE, headers=user["headers"])
    await client.post("/notifications/push/subscriptions", json=SUBSCRIBE, headers=_auth_headers(other))
    assert (await client.get("/notifications/push/subscriptions", headers=user["headers"])).json() == []
    assert len((await client.get("/notifications/push/subscriptions", headers=_auth_headers(other))).json()) == 1


@pytest.mark.asyncio
async def test_opened_marks_read_with_the_push_token_only(client: AsyncClient, db, user):
    n = await _notification(db, user["id"])
    db.add(PushDelivery(notification_id=n.id, user_id=user["id"], type=n.type, status=PushDeliveryStatus.SENT))
    await db.commit()

    bad = await client.post(f"/notifications/{n.id}/opened", params={"token": push.open_token(uuid.uuid4(), uuid.uuid4())})
    assert bad.status_code == 403
    ok = await client.post(f"/notifications/{n.id}/opened", params={"token": push.open_token(user["id"], n.id)})
    assert ok.status_code == 204
    await db.refresh(n)
    assert n.is_read is True
    d = (await db.execute(select(PushDelivery).where(PushDelivery.notification_id == n.id))).scalar_one()
    await db.refresh(d)
    assert d.opened_at is not None


@pytest.mark.asyncio
async def test_push_settings_on_preferences(client: AsyncClient, user):
    h = user["headers"]
    prefs = (await client.get("/users/me/preferences", headers=h)).json()
    assert prefs["push_your_move"] == "SOUND" and prefs["push_heads_up"] == "SILENT"
    assert prefs["quiet_start"] == "22:00:00" and prefs["push_hide_amounts"] is False

    resp = await client.patch("/users/me/preferences", headers=h, json={
        "push_heads_up": "OFF", "quiet_start": "23:30", "push_hide_amounts": True,
    })
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["push_heads_up"] == "OFF" and body["quiet_start"] == "23:30:00" and body["push_hide_amounts"] is True
    assert body["lite_mode"] is False  # untouched

    bad = await client.patch("/users/me/preferences", headers=h, json={"timezone": "Mars/Olympus"})
    assert bad.status_code == 422


@pytest.mark.asyncio
async def test_notification_preferences_carry_push_and_tier(client: AsyncClient, user):
    h = user["headers"]
    items = {p["type"]: p for p in (await client.get("/notifications/preferences", headers=h)).json()["preferences"]}
    assert items["OFFER_RECEIVED"]["push_enabled"] is True and items["OFFER_RECEIVED"]["tier"] == "YOUR_MOVE"
    assert items["DEAL_COMPLETED"]["tier"] == "FYI"

    resp = await client.patch("/notifications/preferences/OFFER_RECEIVED", headers=h, json={"push_enabled": False})
    items = {p["type"]: p for p in resp.json()["preferences"]}
    assert items["OFFER_RECEIVED"]["push_enabled"] is False
    assert items["OFFER_RECEIVED"]["enabled"] is True and items["OFFER_RECEIVED"]["email_enabled"] is True
