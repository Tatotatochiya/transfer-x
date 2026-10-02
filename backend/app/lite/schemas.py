from datetime import time

from pydantic import BaseModel, Field, field_validator

from app.lite.models import PushMode, TextScale


class PreferencesResponse(BaseModel):
    lite_mode: bool
    # True while the user has never chosen: lite_mode is then the default for
    # their role, which may change (e.g. when Lite's role default is switched on).
    lite_mode_is_default: bool
    text_scale: TextScale
    # Phone notifications (docs/feature_spec/mobile-notifications §4.1).
    push_your_move: PushMode = PushMode.SOUND
    push_heads_up: PushMode = PushMode.SILENT
    push_summary: bool = True
    summary_local_time: time = time(8, 0)
    quiet_hours_enabled: bool = True
    quiet_start: time = time(22, 0)
    quiet_end: time = time(7, 0)
    timezone: str = "Europe/London"
    push_hide_amounts: bool = False


class PreferencesUpdateRequest(BaseModel):
    lite_mode: bool | None = None
    text_scale: TextScale | None = None
    push_your_move: PushMode | None = None
    push_heads_up: PushMode | None = None
    push_summary: bool | None = None
    summary_local_time: time | None = None
    quiet_hours_enabled: bool | None = None
    quiet_start: time | None = None
    quiet_end: time | None = None
    timezone: str | None = Field(default=None, max_length=64)
    push_hide_amounts: bool | None = None

    @field_validator("timezone")
    @classmethod
    def _known_timezone(cls, v: str | None) -> str | None:
        from app.notifications.push import valid_timezone

        if v is not None and not valid_timezone(v):
            raise ValueError("Unknown timezone")
        return v

    @field_validator("summary_local_time", "quiet_start", "quiet_end")
    @classmethod
    def _whole_minutes(cls, v: time | None) -> time | None:
        return v.replace(second=0, microsecond=0) if v is not None else v


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
