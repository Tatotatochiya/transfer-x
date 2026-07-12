import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


# ── Shared ────────────────────────────────────────────────────────────────────


class AdminReasonRequest(BaseModel):
    """Reason required for a destructive/overriding admin action — recorded in
    the audit trail so the intervention is explainable later, not just logged
    as "an admin did something"."""
    reason: str


# ── User schemas ──────────────────────────────────────────────────────────────


class AdminUserResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    email: str
    is_active: bool
    is_superuser: bool
    created_at: datetime


class AdminUserUpdateRequest(BaseModel):
    is_active: bool | None = None
    is_superuser: bool | None = None


class AdminCreateUserRequest(BaseModel):
    email: str
    password: str


class AdminResetPasswordRequest(BaseModel):
    new_password: str


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
    transfer_budget_total: Decimal | None = None
    wage_budget_total_weekly: Decimal | None = None


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
    email: str
    password: str
    role: str = "READONLY"  # SPORTING_DIRECTOR, MANAGER, SCOUT, or READONLY


class UpdateStaffRoleRequest(BaseModel):
    role: str  # SPORTING_DIRECTOR, MANAGER, SCOUT, or READONLY


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
    updated_at: datetime
    completed_at: datetime | None = None


# ── System stats ──────────────────────────────────────────────────────────────


class AdminStatsResponse(BaseModel):
    total_users: int
    total_clubs: int
    total_players: int
    active_sales: int      # Sale.status == OPEN
    open_offers: int       # Offer.status in [SENT, COUNTERED]
    active_deals: int      # Deal.status == IN_PROGRESS
    deals_by_stage: dict[str, int]  # AGREEMENT/AGENT_NEGOTIATION/PERSONAL_TERMS/PAPERWORK/CONFIRMED counts (active only)


# ── Activity feed ──────────────────────────────────────────────────────────────


class ActivityItem(BaseModel):
    event_type: str
    message: str
    link: str | None = None
    entity_id: str | None = None
    occurred_at: datetime


# ── Broadcast notification ────────────────────────────────────────────────────


class BroadcastRequest(BaseModel):
    message: str
    link: str | None = None


class BroadcastResponse(BaseModel):
    recipients: int


# ── Health check ──────────────────────────────────────────────────────────────


class HealthIssue(BaseModel):
    severity: str          # "critical" | "warning" | "info"
    category: str          # "deals" | "players" | "sales" | "contracts"
    message: str
    count: int
    details: list[dict]    # list of { id, label } for linking


class HealthReport(BaseModel):
    issues: list[HealthIssue]
    checked_at: datetime
    healthy: bool


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
