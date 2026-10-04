import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator


class AdminReasonRequest(BaseModel):
    """Why an admin is doing something destructive. Recorded in the audit
    trail, and shown to the clubs affected where they are told."""
    reason: str = Field(min_length=5, max_length=500)

    @field_validator("reason")
    @classmethod
    def _trimmed(cls, v: str) -> str:
        v = " ".join(v.split())
        if len(v) < 5:
            raise ValueError("Give a reason of at least 5 characters")
        return v


# ── User schemas ──────────────────────────────────────────────────────────────


class AdminUserResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    email: str
    full_name: str | None = None
    is_active: bool
    is_superuser: bool
    created_at: datetime
    user_type: str | None = None
    last_active_at: datetime | None = None
    # Who they are on TransferX: their club and role, agency, or player.
    club_name: str | None = None
    club_id: uuid.UUID | None = None
    role: str | None = None
    profile_label: str | None = None


class AdminUserUpdateRequest(BaseModel):
    is_active: bool | None = None
    is_superuser: bool | None = None
    # Required when deactivating someone or changing their staff rights.
    reason: str | None = Field(default=None, max_length=500)


class AdminResetLinkRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


class AdminResetLinkResponse(BaseModel):
    """A one-time link for the person to choose a new password. Emailed when
    email is set up, and returned here so it can be shared by hand."""
    url: str
    expires_at: datetime
    emailed: bool


# ── Club schemas ──────────────────────────────────────────────────────────────


class AdminClubFinanceResponse(BaseModel):
    model_config = {"from_attributes": True}

    transfer_budget_total: Decimal
    wage_budget_total_weekly: Decimal
    transfer_reserved: Decimal
    wage_reserved_weekly: Decimal
    transfer_committed: Decimal
    wage_committed_weekly: Decimal
    transfer_remaining: Decimal
    wage_remaining_weekly: Decimal


class AdminClubResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    country: str | None
    city: str | None
    league_name: str | None
    crest_url: str | None
    role: str
    created_at: datetime


class AdminClubDetailResponse(AdminClubResponse):
    finance: AdminClubFinanceResponse | None


class AdminClubUpdateRequest(BaseModel):
    name: str | None = None
    role: str | None = None  # one of BUYER/SELLER/BOTH/ADMIN
    country: str | None = None


class AdminCreateClubRequest(BaseModel):
    user_id: uuid.UUID
    name: str
    role: str = "BOTH"
    country: str | None = None
    league_name: str | None = None
    transfer_budget: Decimal = Decimal("0")
    wage_budget: Decimal = Decimal("0")


class AdminFinancesUpdateRequest(BaseModel):
    transfer_budget_total: Decimal | None = Field(default=None, ge=0)
    wage_budget_total_weekly: Decimal | None = Field(default=None, ge=0)
    reason: str = Field(min_length=5, max_length=500)


# ── Staff schemas ─────────────────────────────────────────────────────────────


class StaffUserResponse(BaseModel):
    """Minimal user info embedded in staff responses."""
    model_config = {"from_attributes": True}

    id: uuid.UUID
    email: str
    is_active: bool


class ClubStaffResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    club_id: uuid.UUID
    user_id: uuid.UUID
    role: str
    created_at: datetime
    user: StaffUserResponse | None = None


class CreateStaffRequest(BaseModel):
    """Invite someone to a club's staff. They choose their own password from
    the invitation link; staff never set one for them."""
    email: str = Field(min_length=3, max_length=254)
    role: str = "READONLY"  # SPORTING_DIRECTOR, MANAGER, SCOUT or READONLY


class StaffInvitationResult(BaseModel):
    email: str
    role: str
    accept_url: str
    expires_at: datetime
    emailed: bool


class ViewAsResponse(BaseModel):
    """A 30-minute, read-only session as the club's owner."""
    access_token: str
    expires_at: datetime
    club_name: str


class UpdateStaffRoleRequest(BaseModel):
    role: str  # MANAGER or READONLY


# ── Player admin schemas ──────────────────────────────────────────────────────


class AdminPlayerUpdateRequest(BaseModel):
    name: str | None = None
    age: int | None = None
    nationality: str | None = None
    position: str | None = None        # GK/DEF/MID/FWD or null
    visibility: str | None = None      # PUBLIC/CLUBS_ONLY/PRIVATE
    status: str | None = None          # CONTRACTED/FREE_AGENT
    open_to_offers: bool | None = None
    photo_url: str | None = None
    current_club_id: uuid.UUID | None = None   # set null to make free agent
    clear_club: bool = False           # explicitly unset current_club_id


# ── Deal admin schemas ─────────────────────────────────────────────────────────


class AdminDealClubSummary(BaseModel):
    model_config = {"from_attributes": True}
    id: uuid.UUID
    name: str


class AdminDealPlayerSummary(BaseModel):
    model_config = {"from_attributes": True}
    id: uuid.UUID
    name: str
    position: str | None = None


class AdminDealResponse(BaseModel):
    model_config = {"from_attributes": True}
    id: uuid.UUID
    player: AdminDealPlayerSummary | None = None
    buyer_club: AdminDealClubSummary | None = None
    seller_club: AdminDealClubSummary | None = None
    agreed_fee: Decimal
    status: str
    stage: str
    created_at: datetime
    completed_at: datetime | None = None


# ── System stats ──────────────────────────────────────────────────────────────


class AdminStatsResponse(BaseModel):
    total_users: int
    total_clubs: int
    total_players: int
    active_sales: int      # Sale.status == OPEN
    open_offers: int       # Offer.status in [SENT, COUNTERED]
    active_deals: int      # Deal.status == IN_PROGRESS
    deals_by_stage: dict[str, int]  # AGREEMENT/PAPERWORK/CONFIRMED counts (active only)


# ── Activity feed ──────────────────────────────────────────────────────────────


class ActivityItem(BaseModel):
    event_type: str
    message: str
    link: str | None = None
    entity_id: str | None = None
    occurred_at: datetime


# ── Broadcast notification ────────────────────────────────────────────────────


class BroadcastRequest(BaseModel):
    message: str = Field(min_length=5, max_length=500)
    # A page inside TransferX ("/sales/…"), never an outside address: a
    # broadcast reaches every user, so it must not be usable for phishing.
    link: str | None = Field(default=None, max_length=300, pattern=r"^/[^/\\].*$|^/$")


class BroadcastResponse(BaseModel):
    recipients: int


# ── Health check ──────────────────────────────────────────────────────────────


class HealthIssue(BaseModel):
    severity: str          # "critical" | "warning" | "info"
    category: str          # "deals" | "players" | "sales" | "contracts"
    message: str
    count: int
    details: list[dict]    # list of { id, label } for linking


class ServiceStatus(BaseModel):
    key: str
    label: str
    ok: bool
    detail: str


class JobStatus(BaseModel):
    id: str
    label: str
    every: str
    last_run_at: datetime | None
    last_ok: bool | None
    last_error: str | None
    next_run_at: datetime | None


class HealthReport(BaseModel):
    issues: list[HealthIssue]
    checked_at: datetime
    healthy: bool
    services: list[ServiceStatus] = []
    jobs: list[JobStatus] = []


# ── Paginated responses ───────────────────────────────────────────────────────


class PaginatedUsers(BaseModel):
    items: list[AdminUserResponse]
    total: int
    page: int
    page_size: int


class PaginatedClubs(BaseModel):
    items: list[AdminClubResponse]
    total: int
    page: int
    page_size: int


# ── World import ──────────────────────────────────────────────────────────────


class ImportWorldTeamRequest(BaseModel):
    user_id: uuid.UUID
    role: str = "BOTH"
    transfer_budget: Decimal = Decimal("0")
    wage_budget: Decimal = Decimal("0")


class ImportSquadRequest(BaseModel):
    club_id: uuid.UUID


class ImportSquadResult(BaseModel):
    imported: int
    skipped: int  # already assigned to a TransferX club
