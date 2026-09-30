from pydantic import BaseModel

from app.lite.models import TextScale


class PreferencesResponse(BaseModel):
    lite_mode: bool
    # True while the user has never chosen: lite_mode is then the default for
    # their role, which may change (e.g. when Lite's role default is switched on).
    lite_mode_is_default: bool
    text_scale: TextScale


class PreferencesUpdateRequest(BaseModel):
    lite_mode: bool | None = None
    text_scale: TextScale | None = None


class LiteWindow(BaseModel):
    state: str  # "open" | "closed" | "none"
    closes_at: str | None = None
    next_opens_at: str | None = None
    days: int | None = None  # until it closes (open) or the next opens (closed)


class LiteMoney(BaseModel):
    transfer_remaining: float
    transfer_budget: float
    wage_remaining_weekly: float
    as_of: str


class LiteWaiting(BaseModel):
    count: int
    club_names: list[str]


class LiteTile(BaseModel):
    key: str
    style: str  # "accent" | "plain" | "offers" | "ai"
    title: str
    subtitle: str
    href: str
    badge: str | None = None
    # Set when the user's role can't do this; the tile shows disabled with the reason.
    disabled_reason: str | None = None


class LiteResume(BaseModel):
    title: str
    href: str


class LiteHomeResponse(BaseModel):
    club_name: str
    window: LiteWindow
    money: LiteMoney | None
    waiting: LiteWaiting
    tiles: list[LiteTile]
    resume: LiteResume | None
    team_contact: dict | None = None  # L7
    briefing_headline: str | None = None


class LiteResumeRequest(BaseModel):
    title: str
    href: str
