import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel

from app.common.schemas import WhoseMove

ColumnKey = Literal["talking", "offers", "fee_agreed", "terms", "paperwork", "done"]


class BoardCard(BaseModel):
    """One player the club is buying or selling, at its furthest point
    (product ADR 0008)."""
    key: str  # side:player_id, stable across refreshes
    side: Literal["BUYING", "SELLING"]
    column: ColumnKey | Literal["closed"]
    kind: Literal["enquiry", "listing", "offer", "bid", "deal"]
    entity_id: uuid.UUID
    player_id: uuid.UUID
    player_name: str
    player_position: str | None = None
    player_photo_url: str | None = None
    counterparty: str | None = None  # masked while an anonymous buyer is hidden
    amount: Decimal | None = None
    detail: str
    whose_move: WhoseMove = WhoseMove.NEITHER
    deadline: datetime | None = None
    link: str
    updated_at: datetime | None = None
    # Other open items for the same player in the same column (e.g. three
    # offers received): the card shows the most pressing one.
    others: int = 0


class BoardColumn(BaseModel):
    key: ColumnKey
    label: str
    cards: list[BoardCard]


class BoardResponse(BaseModel):
    columns: list[BoardColumn]
    closed: list[BoardCard]
    counts: dict[str, int]  # buying / selling / your_move


class BoardHistoryResponse(BaseModel):
    items: list[BoardCard]
    total: int
    page: int
    page_size: int
