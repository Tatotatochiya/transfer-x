import uuid
from datetime import datetime

from typing import Literal

from pydantic import BaseModel, Field

from app.notifications.models import NotificationType, PushPlatform


class NotificationSubject(BaseModel):
    """The player or club a notification is about, for its link and picture."""
    id: uuid.UUID
    name: str
    image_url: str | None = None


class NotificationResponse(BaseModel):
    id: uuid.UUID
    recipient_user_id: uuid.UUID
    type: NotificationType
    message: str
    link: str | None
    is_read: bool
    related_player_id: uuid.UUID | None
    related_club_id: uuid.UUID | None
    created_at: datetime
    # The push's wording and subject (mobile notifications §3.1), so the
    # in-app list can show the same text.
    title: str | None = None
    body: str | None = None
    group_key: str | None = None
    deadline_at: datetime | None = None
    # YOUR_MOVE, HEADS_UP or FYI (app/notifications/tiers.py).
    tier: str | None = None
    player: NotificationSubject | None = None
    club: NotificationSubject | None = None
    model_config = {"from_attributes": True}


class UnreadCountResponse(BaseModel):
    count: int


class NotificationPreferenceItem(BaseModel):
    type: NotificationType
    enabled: bool
    email_enabled: bool
    push_enabled: bool = True
    # YOUR_MOVE, HEADS_UP or FYI. FYI is never pushed: it is counted in the
    # morning summary instead, so its Push switch is shown disabled.
    tier: str


class NotificationPreferencesResponse(BaseModel):
    preferences: list[NotificationPreferenceItem]


class NotificationPreferenceUpdateRequest(BaseModel):
    enabled: bool | None = None
    email_enabled: bool | None = None
    push_enabled: bool | None = None


# ── Web Push (mobile notifications §5.2) ─────────────────────────────────────


class PushPublicKeyResponse(BaseModel):
    # None when the server has no VAPID keys: the app then says push is off.
    key: str | None


class PushKeys(BaseModel):
    p256dh: str = Field(max_length=200)
    auth: str = Field(max_length=200)


class PushSubscribeRequest(BaseModel):
    endpoint: str = Field(max_length=2000)
    keys: PushKeys
    platform: PushPlatform = PushPlatform.OTHER
    timezone: str | None = Field(default=None, max_length=64)


class PushEndpointRequest(BaseModel):
    endpoint: str = Field(max_length=2000)


class PushDeviceResponse(BaseModel):
    id: uuid.UUID
    platform: PushPlatform
    label: str
    endpoint: str
    created_at: datetime
    last_success_at: datetime | None


class PushTestResponse(BaseModel):
    sent: bool
    reason: Literal["sent", "not_configured", "unknown_device", "failed"]
