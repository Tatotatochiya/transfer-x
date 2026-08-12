import enum
from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class Paginated(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int


class WhoseMove(str, enum.Enum):
    """B1: mirrors the WhoseMove type in frontend/src/lib/whoseMove.ts exactly —
    same three string values, same per-entity derivation rules. Shared here
    (not owned by offers/deals/sales individually) so the dashboard, list
    pages and notifications all read one signal, per README.md's own
    instruction that this must be a single server-side source of truth."""
    YOUR = "your"
    THEIR = "their"
    NEITHER = "neither"
