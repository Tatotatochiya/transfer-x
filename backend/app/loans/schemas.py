import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel

from app.loans.models import LoanStatus


class LoanClubSummary(BaseModel):
    id: uuid.UUID
    name: str
    crest_url: str | None = None
    model_config = {"from_attributes": True}


class LoanPlayerSummary(BaseModel):
    id: uuid.UUID
    name: str
    position: str | None = None
    photo_url: str | None = None
    model_config = {"from_attributes": True}


class LoanResponse(BaseModel):
    id: uuid.UUID
    player_id: uuid.UUID
    deal_id: uuid.UUID
    parent_club_id: uuid.UUID
    loanee_club_id: uuid.UUID
    start_date: date
    end_date: date
    loan_fee: Decimal | None = None
    wage_split_pct: Decimal | None = None
    loanee_wage_share: Decimal
    option_to_buy: Decimal | None = None
    obligation_to_buy: bool = False
    recall_allowed: bool = False
    status: LoanStatus
    ended_at: datetime | None = None
    end_reason: str | None = None
    created_at: datetime

    player: LoanPlayerSummary | None = None
    parent_club: LoanClubSummary | None = None
    loanee_club: LoanClubSummary | None = None

    # Which side the *caller* is on. The same row means different things to the
    # two clubs — one is missing a player, the other has borrowed one — and
    # every consumer would otherwise re-derive it by comparing club ids.
    direction: str | None = None

    model_config = {"from_attributes": True}
