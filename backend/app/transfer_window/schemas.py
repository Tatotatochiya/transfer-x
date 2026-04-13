import uuid
from datetime import datetime

from pydantic import BaseModel, model_validator


class TransferWindowCreate(BaseModel):
    name: str
    opens_at: datetime
    closes_at: datetime

    @model_validator(mode="after")
    def check_dates(self):
        if self.closes_at <= self.opens_at:
            raise ValueError("closes_at must be after opens_at")
        return self


class TransferWindowResponse(BaseModel):
    id: uuid.UUID
    name: str
    opens_at: datetime
    closes_at: datetime
    is_open: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class TransferWindowStatus(BaseModel):
    """Lightweight status returned to all clients."""
    enforced: bool           # True if the window system is active (any window exists)
    is_open: bool            # True if currently within a window
    current_window: TransferWindowResponse | None
    next_window: TransferWindowResponse | None
