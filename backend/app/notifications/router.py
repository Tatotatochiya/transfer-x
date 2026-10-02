"""M5 — Notification endpoints."""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.common.schemas import Paginated
from app.config import settings
from app.database import get_db
from app.deps import get_current_user
from app.notifications import push, service
from app.notifications.models import Notification, NotificationType, PushDelivery, PushPlatform, PushSubscription
from app.notifications.schemas import (
    NotificationPreferencesResponse,
    NotificationPreferenceItem,
    NotificationPreferenceUpdateRequest,
    NotificationResponse,
    PushDeviceResponse,
    PushEndpointRequest,
    PushPublicKeyResponse,
    PushSubscribeRequest,
    PushTestResponse,
    UnreadCountResponse,
)
from app.notifications.tiers import tier_of

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=Paginated[NotificationResponse])
async def list_notifications(
    date_from: date | None = None,
    date_to: date | None = None,
    page: int = 1,
    page_size: int = 30,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    notifications, total = await service.list_notifications(
        db, current_user.id, date_from=date_from, date_to=date_to, page=page, page_size=page_size
    )
    return Paginated(
        items=await service.with_subjects(db, notifications),
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/unread-count", response_model=UnreadCountResponse)
async def unread_count(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    count = await service.get_unread_count(db, current_user.id)
    return UnreadCountResponse(count=count)


@router.post("/{notification_id}/read", response_model=NotificationResponse)
async def mark_read(
    notification_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    n = await service.mark_read(db, notification_id, current_user.id)
    if n is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    await db.commit()
    await db.refresh(n)
    return (await service.with_subjects(db, [n]))[0]


@router.post("/read-all", response_model=UnreadCountResponse)
async def mark_all_read(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await service.mark_all_read(db, current_user.id)
    await db.commit()
    return UnreadCountResponse(count=0)


async def _preferences_response(db: AsyncSession, user_id: uuid.UUID) -> NotificationPreferencesResponse:
    disabled = await service.get_disabled_types(db, user_id)
    email_disabled = await service.get_email_disabled_types(db, user_id)
    push_disabled = await service.get_push_disabled_types(db, user_id)
    prefs = [
        NotificationPreferenceItem(
            type=t,
            enabled=(t not in disabled),
            email_enabled=(t not in email_disabled),
            push_enabled=(t not in push_disabled),
            tier=tier_of(t).value,
        )
        for t in NotificationType
    ]
    return NotificationPreferencesResponse(preferences=prefs)


@router.get("/preferences", response_model=NotificationPreferencesResponse)
async def get_preferences(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return all notification types with their enabled/disabled status for this user."""
    return await _preferences_response(db, current_user.id)


@router.patch("/preferences/{type_name}", response_model=NotificationPreferencesResponse)
async def update_preference(
    type_name: str,
    body: NotificationPreferenceUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Enable or disable in-app and/or email delivery for a specific notification type."""
    try:
        ntype = NotificationType(type_name)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown notification type: {type_name}")

    if body.enabled is not None:
        await service.set_preference(db, current_user.id, ntype, body.enabled)
    if body.email_enabled is not None:
        await service.set_email_preference(db, current_user.id, ntype, body.email_enabled)
    if body.push_enabled is not None:
        await service.set_push_preference(db, current_user.id, ntype, body.push_enabled)
    await db.commit()
    return await _preferences_response(db, current_user.id)


# ── Web Push (docs/feature_spec/mobile-notifications §5.2) ───────────────────


def _device_label(platform: PushPlatform, user_agent: str | None) -> str:
    ua = user_agent or ""
    if platform is PushPlatform.IOS_HOME_SCREEN:
        return f"{'iPad' if 'iPad' in ua or 'Macintosh' in ua else 'iPhone'} · Home Screen app"
    browser = next((b for b in ("Edg", "SamsungBrowser", "Firefox", "Chrome", "Safari") if b in ua), None)
    browser = {"Edg": "Edge", "SamsungBrowser": "Samsung Internet"}.get(browser, browser)
    if platform is PushPlatform.ANDROID:
        return f"Android · {browser or 'browser'}"
    system = next((name for key, name in (("Windows", "Windows"), ("Mac OS", "Mac"), ("Linux", "Linux")) if key in ua), None)
    return " · ".join(x for x in (system or "Computer", browser) if x)


def _device(sub: PushSubscription) -> PushDeviceResponse:
    return PushDeviceResponse(
        id=sub.id, platform=sub.platform, label=_device_label(sub.platform, sub.user_agent),
        endpoint=sub.endpoint, created_at=sub.created_at, last_success_at=sub.last_success_at,
    )


@router.get("/push/public-key", response_model=PushPublicKeyResponse)
async def push_public_key():
    """The VAPID public key a browser subscribes with, or null when this
    server doesn't send pushes."""
    return PushPublicKeyResponse(key=settings.vapid_public_key if push.vapid_configured() else None)


@router.get("/push/subscriptions", response_model=list[PushDeviceResponse])
async def list_push_subscriptions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """This user's devices, for the settings screen."""
    subs = (await db.execute(
        select(PushSubscription).where(PushSubscription.user_id == current_user.id)
        .order_by(PushSubscription.created_at.desc())
    )).scalars()
    return [_device(s) for s in subs]


@router.post("/push/subscriptions", response_model=PushDeviceResponse, status_code=status.HTTP_201_CREATED)
async def subscribe_push(
    body: PushSubscribeRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Save this device's subscription. A device belongs to whoever subscribed
    on it last: a shared tablet that someone else signs in to stops getting
    the previous person's pushes."""
    from app.audit import service as audit_service
    from app.lite.service import get_row as get_user_preferences
    from app.lite.models import UserPreference

    sub = (await db.execute(
        select(PushSubscription).where(PushSubscription.endpoint == body.endpoint)
    )).scalar_one_or_none()
    is_new = sub is None or sub.user_id != current_user.id
    if sub is None:
        sub = PushSubscription(endpoint=body.endpoint, user_id=current_user.id)
        db.add(sub)
    sub.user_id = current_user.id
    sub.p256dh = body.keys.p256dh
    sub.auth = body.keys.auth
    sub.platform = body.platform
    sub.user_agent = (request.headers.get("user-agent") or "")[:300] or None
    sub.failure_count = 0

    if body.timezone and push.valid_timezone(body.timezone):
        prefs = await get_user_preferences(db, current_user.id)
        if prefs is None:
            prefs = UserPreference(user_id=current_user.id)
            db.add(prefs)
        prefs.timezone = body.timezone
    await db.flush()
    if is_new:
        await audit_service.emit(
            db, entity_type="push_subscription", entity_id=sub.id, action="push_subscribed",
            actor_user_id=current_user.id, payload={"platform": body.platform.value},
            description=f"Turned on notifications on {_device_label(sub.platform, sub.user_agent)}",
        )
    await db.commit()
    await db.refresh(sub)
    return _device(sub)


@router.delete("/push/subscriptions", status_code=status.HTTP_204_NO_CONTENT)
async def unsubscribe_push(
    body: PushEndpointRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remove a device (this one on sign-out, or another from settings)."""
    from app.audit import service as audit_service

    sub = (await db.execute(select(PushSubscription).where(
        PushSubscription.endpoint == body.endpoint, PushSubscription.user_id == current_user.id,
    ))).scalar_one_or_none()
    if sub is None:
        return None
    await audit_service.emit(
        db, entity_type="push_subscription", entity_id=sub.id, action="push_unsubscribed",
        actor_user_id=current_user.id, payload={"platform": sub.platform.value},
        description=f"Turned off notifications on {_device_label(sub.platform, sub.user_agent)}",
    )
    await db.delete(sub)
    await db.commit()
    return None


@router.post("/push/test", response_model=PushTestResponse)
async def test_push(
    body: PushEndpointRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Send "Notifications are working" to one of this user's devices."""
    if not push.vapid_configured():
        return PushTestResponse(sent=False, reason="not_configured")
    sub = (await db.execute(select(PushSubscription).where(
        PushSubscription.endpoint == body.endpoint, PushSubscription.user_id == current_user.id,
    ))).scalar_one_or_none()
    if sub is None:
        return PushTestResponse(sent=False, reason="unknown_device")
    ok = await push.send_test(db, sub)
    await db.commit()
    return PushTestResponse(sent=ok, reason="sent" if ok else "failed")


@router.post("/{notification_id}/opened", status_code=status.HTTP_204_NO_CONTENT)
async def push_opened(
    notification_id: uuid.UUID,
    token: str,
    db: AsyncSession = Depends(get_db),
):
    """The service worker reports a tap on a push: marks the notification read
    and records when it was opened. Authorised by the push's own token, not
    a login (the service worker has no access token)."""
    from datetime import datetime, timezone

    user_id = push.read_open_token(token, notification_id)
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid or expired link")
    n = await db.get(Notification, notification_id)
    if n is None or n.recipient_user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    n.is_read = True
    now = datetime.now(timezone.utc)
    deliveries = (await db.execute(select(PushDelivery).where(
        PushDelivery.notification_id == notification_id, PushDelivery.opened_at.is_(None),
    ))).scalars()
    for d in deliveries:
        d.opened_at = now
    await db.commit()
    return None
