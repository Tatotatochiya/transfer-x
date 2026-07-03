"""M5 — Notification endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.common.schemas import Paginated
from app.database import get_db
from app.deps import get_current_user
from app.notifications import service
from app.notifications.models import NotificationType
from app.notifications.schemas import (
    NotificationPreferencesResponse,
    NotificationPreferenceItem,
    NotificationPreferenceUpdateRequest,
    NotificationResponse,
    UnreadCountResponse,
)

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=Paginated[NotificationResponse])
async def list_notifications(
    page: int = 1,
    page_size: int = 30,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    notifications, total = await service.list_notifications(
        db, current_user.id, page=page, page_size=page_size
    )
    return Paginated(
        items=[NotificationResponse.model_validate(n) for n in notifications],
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
    return NotificationResponse.model_validate(n)


@router.post("/read-all", response_model=UnreadCountResponse)
async def mark_all_read(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await service.mark_all_read(db, current_user.id)
    await db.commit()
    return UnreadCountResponse(count=0)


def _build_preferences_response(
    disabled: set[NotificationType], email_disabled: set[NotificationType]
) -> NotificationPreferencesResponse:
    prefs = [
        NotificationPreferenceItem(
            type=t, enabled=(t not in disabled), email_enabled=(t not in email_disabled)
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
    disabled = await service.get_disabled_types(db, current_user.id)
    email_disabled = await service.get_email_disabled_types(db, current_user.id)
    return _build_preferences_response(disabled, email_disabled)


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
    await db.commit()

    disabled = await service.get_disabled_types(db, current_user.id)
    email_disabled = await service.get_email_disabled_types(db, current_user.id)
    return _build_preferences_response(disabled, email_disabled)
