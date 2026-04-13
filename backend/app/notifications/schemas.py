import uuid
from datetime import datetime

from pydantic import BaseModel

from app.notifications.models import NotificationType


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
    model_config = {"from_attributes": True}


class UnreadCountResponse(BaseModel):
    count: int


class NotificationPreferenceItem(BaseModel):
    type: NotificationType
    enabled: bool


class NotificationPreferencesResponse(BaseModel):
    preferences: list[NotificationPreferenceItem]


class NotificationPreferenceUpdateRequest(BaseModel):
    enabled: bool
