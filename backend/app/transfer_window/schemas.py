import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field, model_validator


class TransferWindowCreate(BaseModel):
    name: str
    opens_at: datetime
    closes_at: datetime
    # The country whose clubs it governs; none means every club.
    country: str | None = Field(default=None, max_length=100)
    # Where the dates came from (FIFA's registration period calendar, the
    # league's announcement) and when someone checked them.
    source_url: str | None = Field(default=None, max_length=500)
    checked_on: date | None = None

    @model_validator(mode="after")
    def check_dates(self):
        if self.closes_at <= self.opens_at:
            raise ValueError("closes_at must be after opens_at")
        if self.source_url and not self.source_url.strip().lower().startswith(("http://", "https://")):
            raise ValueError("source_url must be a web address")
        return self


class TransferWindowResponse(BaseModel):
    id: uuid.UUID
    name: str
    country: str | None = None
    opens_at: datetime
    closes_at: datetime
    source_url: str | None = None
    checked_on: date | None = None
    is_open: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class TransferWindowStatus(BaseModel):
    """Lightweight status returned to all clients: for a signed-in club user,
    the windows of the club's country."""
    enforced: bool           # True if any window governs the caller's club
    is_open: bool            # True if currently within a window
    country: str | None = None
    current_window: TransferWindowResponse | None
    next_window: TransferWindowResponse | None


class WindowCoverage(BaseModel):
    """One country with clubs on TransferX, for the admin's reminder."""
    country: str
    own_windows: bool        # False: it follows the windows with no country
    current_window: TransferWindowResponse | None
    next_window: TransferWindowResponse | None
    missing: bool            # nothing open or opening in the next six months
