import uuid
from datetime import datetime

from pydantic import BaseModel, model_validator


class TransferWindowCreate(BaseModel):
    name: str
    association: str | None = None
    opens_at: datetime
    closes_at: datetime
    grace_period_hours: int = 24

    @model_validator(mode="after")
    def check_dates(self):
        if self.closes_at <= self.opens_at:
            raise ValueError("closes_at must be after opens_at")
        return self


class TransferWindowUpdate(BaseModel):
    """Admin override of an existing window. All fields optional — only supplied
    fields are changed. closes_at > opens_at is validated against the resulting
    window (using whichever of the two wasn't supplied), not this payload alone."""
    name: str | None = None
    association: str | None = None
    opens_at: datetime | None = None
    closes_at: datetime | None = None
    grace_period_hours: int | None = None


class TransferWindowResponse(BaseModel):
    id: uuid.UUID
    name: str
    association: str | None = None
    opens_at: datetime
    closes_at: datetime
    grace_period_hours: int
    is_open: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class TransferWindowStatus(BaseModel):
    """Lightweight status returned to all clients, scoped to the requested association."""
    association: str | None = None  # the association this status was resolved for
    enforced: bool           # True if any window applies to this association
    is_open: bool            # True if currently within a window
    current_window: TransferWindowResponse | None
    next_window: TransferWindowResponse | None
