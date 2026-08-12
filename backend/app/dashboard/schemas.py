import uuid
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel


class DashboardItem(BaseModel):
    """B2: one tier-1 'waiting on you' card. `kind` + `id` are enough to
    identify the underlying entity; the rest is display-ready summary data so
    the dashboard can render without a follow-up fetch per row."""
    kind: Literal["approval", "deal", "offer", "sale"]
    id: uuid.UUID
    player_name: str | None = None
    club_name: str | None = None
    amount: Decimal | None = None
    reason: str
    link: str


class DashboardResponse(BaseModel):
    waiting_on_you: list[DashboardItem]
