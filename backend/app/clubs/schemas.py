import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, EmailStr

from app.clubs.models import ClubRole, StaffRole




class ClubFinanceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    transfer_budget_total: Decimal
    wage_budget_total_weekly: Decimal
    transfer_reserved: Decimal
    wage_reserved_weekly: Decimal
    transfer_committed: Decimal
    transfer_spent: Decimal
    wage_committed_weekly: Decimal
    transfer_remaining: Decimal
    wage_remaining_weekly: Decimal
    approval_threshold: Decimal | None = None
    updated_at: datetime


class ClubResponse(BaseModel):
    """Full club view — returned to the owning user or staff."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    country: str | None
    city: str | None
    league_name: str | None
    crest_url: str | None
    role: ClubRole
    verified: bool
    created_at: datetime
    finance: ClubFinanceResponse | None = None
    my_role: str | None = None  # OWNER | MANAGER | READONLY — set by router, not DB


class ClubPublicResponse(BaseModel):
    """Minimal club view — returned in public lists and on player cards."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    country: str | None
    city: str | None
    league_name: str | None
    crest_url: str | None
    role: ClubRole
    verified: bool
    created_at: datetime


class ClubMembershipResponse(BaseModel):
    """TRA-151 (D3): the caller's club, role, and server-derived capability list."""
    club: ClubPublicResponse
    role: str  # OWNER | SPORTING_DIRECTOR | MANAGER | SCOUT | READONLY
    capabilities: list[str]


class ClubUpdateRequest(BaseModel):
    name: str | None = None
    country: str | None = None
    city: str | None = None
    league_name: str | None = None
    crest_url: str | None = None


# ── Team management (TRA-86) ─────────────────────────────────────────────────

class ClubStaffMemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    email: str  # set by router from the joined user
    role: StaffRole
    created_at: datetime


class ClubStaffInvitationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    role: StaffRole
    created_at: datetime
    expires_at: datetime


class TeamResponse(BaseModel):
    """Active staff + live pending invitations, in one payload."""
    staff: list[ClubStaffMemberResponse]
    invitations: list[ClubStaffInvitationResponse]


class StaffInviteRequest(BaseModel):
    email: EmailStr
    role: StaffRole


class StaffInviteResponse(BaseModel):
    invitation: ClubStaffInvitationResponse
    # Returned exactly once, at creation — the raw token is never stored (D6).
    accept_url: str


class StaffRoleUpdateRequest(BaseModel):
    role: StaffRole


class InvitationPreviewResponse(BaseModel):
    """Public preview for the accept page — no ids, nothing sensitive."""
    club_name: str
    club_crest_url: str | None
    role: StaffRole
    email: str
    expires_at: datetime


class InvitationAcceptRequest(BaseModel):
    password: str


# ── Player search views ───────────────────────────────────────────────────────

class PlayerSearchViewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    club_id: uuid.UUID
    name: str
    filters: dict
    is_default: bool
    created_at: datetime
    updated_at: datetime


class PlayerSearchViewCreateRequest(BaseModel):
    name: str
    filters: dict = {}
    is_default: bool = False


class PlayerSearchViewUpdateRequest(BaseModel):
    name: str | None = None
    filters: dict | None = None
    is_default: bool | None = None
