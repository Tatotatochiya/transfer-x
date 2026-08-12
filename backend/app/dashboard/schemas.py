import uuid
from datetime import datetime
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
    # When the chance to act runs out — an approval's TTL, an offer's expiry, an
    # auction's close. Null for deals, which have no per-stage deadline (the
    # `deal_sla` job is the closest thing and doesn't set one). Urgency is half
    # of "waiting on you", so a consumer that only had `reason` would have to
    # re-fetch each entity to show a countdown.
    deadline: datetime | None = None


class DashboardResponse(BaseModel):
    waiting_on_you: list[DashboardItem]
