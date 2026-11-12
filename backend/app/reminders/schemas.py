from datetime import datetime

from pydantic import BaseModel, Field


class ReminderHolder(BaseModel):
    kind: str            # "club", "agent" or "player"
    name: str


class LastReminder(BaseModel):
    at: datetime
    by: str              # "Tottenham", "Sofia Reyes" or "TransferX"
    escalated: bool
    note: str | None = None
    # Sent by the viewer's own club (or the viewer), so it reads "You reminded…".
    by_you: bool = False


class ReminderState(BaseModel):
    holder: ReminderHolder | None = None
    waiting_since: datetime | None = None
    can_send: bool
    reason: str | None = None
    next_allowed_at: datetime | None = None
    would_escalate: bool = False
    # The exact sentence the holder will get.
    preview: str | None = None
    last: LastReminder | None = None
    # A reminder sent to the viewer (they hold the move): shown in red on their card.
    to_you: LastReminder | None = None


class SendReminder(BaseModel):
    note: str | None = Field(default=None, max_length=200)
