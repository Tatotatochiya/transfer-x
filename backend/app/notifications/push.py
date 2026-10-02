"""Web Push: notifications on the phone lock screen (docs/feature_spec/mobile-notifications §5).

A notification is pushed only **after the transaction that created it
commits**. `create_notification` calls `queue_push`, which notes the id on the
session; a session `after_commit` hook then starts the send in its own task
and its own session. Sending from inside the request (as the email does)
would race the commit: the task could look for a row that isn't there yet,
or push something the request then rolled back.

For each notification `deliver` decides, and records in `push_deliveries`:
1. the tier (FYI is never pushed) and the person's settings;
2. a repeat check, for the scheduled reminders only;
3. quiet hours: hold the push until they end, unless it is the person's move
   and the deadline falls before quiet hours end (plus an hour);
4. send to each of the person's devices.

The payload carries both shapes in one message: iOS 18.4+ shows the
declarative `web_push: 8030` notification itself, every other browser's
service worker reads the same `notification` object. A push only ever opens
a page; nothing is accepted or sent from the lock screen (ADR 0006).

Without VAPID keys (local development, tests) nothing is pushed, the same
way email is skipped without SMTP_HOST.
"""
import asyncio
import base64
import hashlib
import json
import logging
import time as _time
import uuid
from datetime import datetime, time, timedelta, timezone
from urllib.parse import urlencode
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from jose import JWTError, jwt
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.config import settings
from app.lite.models import PushMode, UserPreference
from app.notifications.models import (
    Notification,
    NotificationPreference,
    NotificationType,
    PushDelivery,
    PushDeliveryStatus,
    PushSubscription,
)
from app.notifications.tiers import HIDDEN_BODY, Tier, hidden_title, tier_of

logger = logging.getLogger(__name__)

# The scheduled reminders. The hourly job tells each person once (see
# notifications.service, `once=True`); this is the second guard, so a
# reminder is never pushed twice within REPEAT_WINDOW. Event-driven types are
# not checked: a second counter-offer on the same offer is news.
REMINDER_TYPES = {NotificationType.OFFER_EXPIRING, NotificationType.AUCTION_ENDING, NotificationType.INSTALMENT_DUE}
REPEAT_WINDOW = timedelta(hours=20)

# Review decision 2: a "your move" push breaks through quiet hours when its
# deadline would pass before the person is likely to see it, i.e. before
# quiet hours end plus this margin.
DEADLINE_MARGIN = timedelta(hours=1)

PUSH_TTL_SECONDS = 86_400
MAX_FAILURES = 5
OPEN_TOKEN_DAYS = 8  # longer than the push's own 24-hour TTL
DEFAULT_TZ = "Europe/London"


def vapid_configured() -> bool:
    return bool(settings.vapid_public_key and settings.vapid_private_key and settings.vapid_subject)


# ── Queue on the session, send after commit ──────────────────────────────────

_PENDING = "pending_push_ids"
_tasks: set[asyncio.Task] = set()  # strong references until each send finishes


def queue_push(db: AsyncSession, notification_id: uuid.UUID) -> None:
    if not vapid_configured():
        return
    db.sync_session.info.setdefault(_PENDING, []).append(notification_id)


@event.listens_for(Session, "after_commit")
def _after_commit(session: Session) -> None:
    ids = session.info.pop(_PENDING, None)
    if not ids:
        return
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:  # a synchronous script: no loop to send from
        return
    for nid in ids:
        task = loop.create_task(send_for_notification(nid))
        _tasks.add(task)
        task.add_done_callback(_tasks.discard)


@event.listens_for(Session, "after_rollback")
def _after_rollback(session: Session) -> None:
    session.info.pop(_PENDING, None)


async def send_for_notification(notification_id: uuid.UUID) -> None:
    """The task started after commit. Its own session, never the request's."""
    from app.database import AsyncSessionLocal

    try:
        async with AsyncSessionLocal() as db:
            n = await db.get(Notification, notification_id)
            if n is not None:
                await deliver(db, n, datetime.now(timezone.utc))
                await db.commit()
    except Exception:
        logger.exception("Push for notification %s failed", notification_id)


# ── Settings ─────────────────────────────────────────────────────────────────


def _zone(name: str | None) -> ZoneInfo:
    try:
        return ZoneInfo(name or DEFAULT_TZ)
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo(DEFAULT_TZ)


def valid_timezone(name: str) -> bool:
    try:
        ZoneInfo(name)
        return True
    except (ZoneInfoNotFoundError, ValueError):
        return False


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def quiet_until(prefs: UserPreference | None, now: datetime) -> datetime | None:
    """When quiet hours end, if `now` is inside them; otherwise None. The
    window may wrap midnight (22:00 to 07:00)."""
    enabled = prefs.quiet_hours_enabled if prefs is not None else True
    if not enabled:
        return None
    start = prefs.quiet_start if prefs is not None else time(22, 0)
    end = prefs.quiet_end if prefs is not None else time(7, 0)
    if start == end:
        return None
    zone = _zone(prefs.timezone if prefs is not None else None)
    local = _aware(now).astimezone(zone)
    t = local.time()
    inside = (start <= t < end) if start < end else (t >= start or t < end)
    if not inside:
        return None
    end_at = datetime.combine(local.date(), end, tzinfo=zone)
    if end_at <= local:
        end_at += timedelta(days=1)
    return end_at.astimezone(timezone.utc)


def _mode(prefs: UserPreference | None, tier: Tier) -> PushMode:
    if tier is Tier.YOUR_MOVE:
        return prefs.push_your_move if prefs is not None else PushMode.SOUND
    if tier is Tier.HEADS_UP:
        return prefs.push_heads_up if prefs is not None else PushMode.SILENT
    return PushMode.OFF


# ── Deciding ─────────────────────────────────────────────────────────────────


async def deliver(db: AsyncSession, n: Notification, now: datetime) -> PushDelivery | None:
    """Decide what happens to one notification and record it. Returns the
    delivery row, or None when the push simply doesn't apply (FYI, switched
    off, no device)."""
    tier = tier_of(n.type)
    if tier is Tier.FYI:
        return None
    user_id = n.recipient_user_id
    type_pref = (await db.execute(select(NotificationPreference).where(
        NotificationPreference.user_id == user_id, NotificationPreference.type == n.type,
    ))).scalar_one_or_none()
    if type_pref is not None and not (type_pref.enabled and type_pref.push_enabled):
        return None
    prefs = await db.get(UserPreference, user_id)
    if _mode(prefs, tier) is PushMode.OFF:
        return None
    subs = await _subscriptions(db, user_id)
    if not subs:
        return None

    # Checked before this delivery is added, or the query would find it.
    repeat = n.type in REMINDER_TYPES and bool(n.group_key) and await _pushed_recently(
        db, user_id, n.type, n.group_key, now)
    delivery = PushDelivery(notification_id=n.id, user_id=user_id, type=n.type, group_key=n.group_key,
                            status=PushDeliveryStatus.SENT)
    db.add(delivery)

    if repeat:
        delivery.status = PushDeliveryStatus.SKIPPED_DUPLICATE
        await db.flush()
        return delivery

    held_until = quiet_until(prefs, now)
    if held_until is not None and not _breaks_through(tier, n.deadline_at, held_until):
        delivery.status = PushDeliveryStatus.HELD
        delivery.send_after = held_until
        await db.flush()
        return delivery

    await _send_to_devices(db, n, prefs, tier, subs, delivery, now)
    return delivery


def _breaks_through(tier: Tier, deadline_at: datetime | None, quiet_end: datetime) -> bool:
    return tier is Tier.YOUR_MOVE and deadline_at is not None and _aware(deadline_at) <= quiet_end + DEADLINE_MARGIN


async def _subscriptions(db: AsyncSession, user_id: uuid.UUID) -> list[PushSubscription]:
    return list((await db.execute(
        select(PushSubscription).where(PushSubscription.user_id == user_id)
    )).scalars())


async def _pushed_recently(db: AsyncSession, user_id, type_, group_key: str, now: datetime) -> bool:
    row = (await db.execute(select(PushDelivery.id).where(
        PushDelivery.user_id == user_id,
        PushDelivery.type == type_,
        PushDelivery.group_key == group_key,
        PushDelivery.status.in_([PushDeliveryStatus.SENT, PushDeliveryStatus.HELD]),
        PushDelivery.created_at >= now - REPEAT_WINDOW,
    ).limit(1))).first()
    return row is not None


async def release_held_pushes(db: AsyncSession, now: datetime) -> int:
    """Scheduler (every 5 minutes): send what quiet hours held back. A
    notification read in the meantime is not pushed."""
    held = list((await db.execute(select(PushDelivery).where(
        PushDelivery.status == PushDeliveryStatus.HELD, PushDelivery.send_after <= now,
    ))).scalars())
    for delivery in held:
        n = await db.get(Notification, delivery.notification_id) if delivery.notification_id else None
        if n is None or n.is_read:
            delivery.status = PushDeliveryStatus.SKIPPED
            continue
        subs = await _subscriptions(db, delivery.user_id)
        if not subs:
            delivery.status = PushDeliveryStatus.SKIPPED
            continue
        prefs = await db.get(UserPreference, delivery.user_id)
        delivery.status = PushDeliveryStatus.SENT
        await _send_to_devices(db, n, prefs, tier_of(n.type), subs, delivery, now)
    await db.flush()
    return len(held)


# ── Payload ──────────────────────────────────────────────────────────────────


def open_token(user_id: uuid.UUID, notification_id: uuid.UUID) -> str:
    """Lets the service worker report a tap. It can't reach the access token
    (that lives in the page's memory), so each push carries its own token,
    good for this one notification only."""
    exp = datetime.now(timezone.utc) + timedelta(days=OPEN_TOKEN_DAYS)
    return jwt.encode(
        {"sub": str(user_id), "nid": str(notification_id), "purpose": "push_open", "exp": exp},
        settings.jwt_secret_key, algorithm=settings.jwt_algorithm,
    )


def read_open_token(token: str, notification_id: uuid.UUID) -> uuid.UUID | None:
    try:
        claims = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None
    if claims.get("purpose") != "push_open" or claims.get("nid") != str(notification_id):
        return None
    return uuid.UUID(claims["sub"])


def _url(path: str | None, nid: uuid.UUID, extra: dict | None = None) -> str:
    path = path or "/notifications"
    if path.startswith("http"):
        base = path
    else:
        base = f"{settings.frontend_base_url.rstrip('/')}{path if path.startswith('/') else '/' + path}"
    params = {"from": "push", **(extra or {}), "nid": str(nid)}
    return f"{base}{'&' if '?' in base else '?'}{urlencode(params)}"


def build_payload(
    n: Notification, *, tier: Tier, silent: bool, hide_amounts: bool, badge: int | None,
    tz: ZoneInfo | None = None, now: datetime | None = None,
) -> dict:
    from app.notifications.copy import render

    if hide_amounts:
        title, body = hidden_title(n.type), HIDDEN_BODY
        actions = []  # an action's label can carry a figure ("Ask for £21m")
    else:
        # Deadlines are written in the recipient's own timezone (copy.render).
        zone, at = tz or _zone(None), now or datetime.now(timezone.utc)
        title = render(n.title or n.message, n.deadline_at, zone, at)[:120]
        body = render(n.body, n.deadline_at, zone, at)
        actions = [
            {"action": a["action"], "title": a["title"], "navigate": _url(a["url"], n.id)}
            for a in (n.actions_json or [])[:2]
        ]
    notification = {
        "title": title,
        "navigate": _url(n.link, n.id),
        "tag": n.group_key or f"n:{n.id}",
        "silent": silent,
        "lang": "en-GB",
        "data": {
            "nid": str(n.id),
            "tier": tier.value,
            # For the classic service worker; kept out of the declarative keys.
            "renotify": tier is Tier.YOUR_MOVE,
            "open_token": open_token(n.recipient_user_id, n.id),
        },
    }
    if body:
        notification["body"] = body
    if actions:
        notification["actions"] = actions
    if badge is not None:
        notification["app_badge"] = str(badge)
    return {"web_push": 8030, "notification": notification}


def topic_for(group_key: str | None) -> str | None:
    """The Topic header: a newer undelivered push for the same subject
    replaces the older one at the push service. At most 32 URL-safe chars."""
    if not group_key:
        return None
    digest = hashlib.sha256(group_key.encode()).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")[:32]


# The app badge counts what is waiting on the person (the Dashboard's
# "waiting on you"), recomputed per push but at most once a minute each.
_badge_cache: dict[uuid.UUID, tuple[float, int | None]] = {}


async def _badge_count(db: AsyncSession, user_id: uuid.UUID) -> int | None:
    hit = _badge_cache.get(user_id)
    if hit is not None and hit[0] > _time.monotonic():
        return hit[1]
    count: int | None = None
    try:
        from app.auth.models import User
        from app.clubs.service import get_club_and_role_for_user
        from app.dashboard import service as dashboard_service

        user = await db.get(User, user_id)
        club, _role = await get_club_and_role_for_user(db, user_id)
        if user is not None and club is not None:
            count = len((await dashboard_service.get_dashboard(db, club=club, current_user=user)).waiting_on_you)
    except Exception:
        logger.exception("Badge count for %s failed", user_id)
    _badge_cache[user_id] = (_time.monotonic() + 60, count)
    return count


# ── Sending ──────────────────────────────────────────────────────────────────


async def _send_to_devices(
    db: AsyncSession, n: Notification, prefs: UserPreference | None, tier: Tier,
    subs: list[PushSubscription], delivery: PushDelivery, now: datetime,
) -> None:
    payload = build_payload(
        n, tier=tier,
        silent=_mode(prefs, tier) is not PushMode.SOUND,
        hide_amounts=prefs.push_hide_amounts if prefs is not None else False,
        badge=await _badge_count(db, n.recipient_user_id),
        tz=_zone(prefs.timezone if prefs is not None else None),
        now=now,
    )
    headers = {"Urgency": "high" if tier is Tier.YOUR_MOVE else "normal"}
    if (topic := topic_for(n.group_key)) is not None:
        headers["Topic"] = topic
    sent = 0
    for sub in subs:
        if await send_one(db, sub, payload, headers, now):
            sent += 1
    delivery.status = PushDeliveryStatus.SENT if sent else PushDeliveryStatus.FAILED
    delivery.sent_at = now if sent else None
    await db.flush()


async def send_one(db: AsyncSession, sub: PushSubscription, payload: dict, headers: dict, now: datetime) -> bool:
    """Send to one device. A 404 or 410 means the device unsubscribed, so the
    subscription is deleted; other failures are counted, and the subscription
    goes after MAX_FAILURES in a row."""
    status = await _post(sub, payload, headers)
    if status is not None and status < 300:
        sub.last_success_at = now
        sub.failure_count = 0
        return True
    if status in (404, 410):
        await db.delete(sub)
        return False
    sub.last_failure_at = now
    sub.failure_count = (sub.failure_count or 0) + 1
    if sub.failure_count >= MAX_FAILURES:
        await db.delete(sub)
    return False


async def _post(sub: PushSubscription, payload: dict, headers: dict) -> int | None:
    """The HTTP status from the push service, or None if it couldn't be reached.
    Separate so tests can replace it."""
    from pywebpush import WebPushException, webpush

    def _send() -> int | None:
        try:
            resp = webpush(
                subscription_info={"endpoint": sub.endpoint, "keys": {"p256dh": sub.p256dh, "auth": sub.auth}},
                data=json.dumps(payload),
                vapid_private_key=settings.vapid_private_key,
                vapid_claims={"sub": settings.vapid_subject},
                ttl=PUSH_TTL_SECONDS,
                headers=headers,
            )
            return resp.status_code
        except WebPushException as exc:
            return exc.response.status_code if exc.response is not None else None
        except Exception:
            logger.exception("Push to %s failed", sub.endpoint[:60])
            return None

    return await asyncio.to_thread(_send)


async def send_test(db: AsyncSession, sub: PushSubscription) -> bool:
    payload = {"web_push": 8030, "notification": {
        "title": "Notifications are working",
        "body": "This is how TransferX will reach you on this device.",
        "navigate": f"{settings.frontend_base_url.rstrip('/')}/account",
        "tag": "test", "silent": False, "lang": "en-GB", "data": {"tier": "TEST"},
    }}
    return await send_one(db, sub, payload, {"Urgency": "high"}, datetime.now(timezone.utc))
