import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.auth.models import UserType


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    user_type: UserType = UserType.CLUB
    club_name: str = ""  # Defaults to email prefix if empty (CLUB only)
    # Agent fields
    display_name: str = ""
    agency_name: str = ""
    licence_no: str | None = None
    country: str = ""
    # Player fields
    player_id: uuid.UUID | None = None


class LoginRequest(BaseModel):
    # An email address or a username. A username is the part of the email
    # before the "@" (product decision, 2026-09-29), so there is no separate
    # username to register; the field keeps its name for existing clients.
    email: str = Field(min_length=1, max_length=254)
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    is_active: bool
    is_superuser: bool
    user_type: UserType
    created_at: datetime
    # Owner or staff of a club. TransferX staff accounts have none, so the app
    # shows them the admin sidebar and skips club-only requests.
    has_club: bool = False
    # Set when this is a read-only "view as this club" session: the email of
    # the TransferX staff member looking.
    viewed_by: str | None = None


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str
