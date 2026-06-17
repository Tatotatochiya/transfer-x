import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr

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
    email: EmailStr
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


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str
