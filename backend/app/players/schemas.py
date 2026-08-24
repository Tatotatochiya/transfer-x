import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.players.models import PlayerPosition, PlayerStatus, PlayerVisibility, ValuationSource, WageSource


class ContractResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    club_id: uuid.UUID
    start_date: date | None
    end_date: date | None
    wage_weekly: Decimal | None
    release_clause: Decimal | None
    club_valuation: Decimal | None
    is_active: bool
    notes: str | None
    created_at: datetime


class ContractCreateRequest(BaseModel):
    club_id: uuid.UUID
    start_date: date | None = None
    end_date: date | None = None
    wage_weekly: Decimal | None = None
    release_clause: Decimal | None = None
    notes: str | None = None


# Minimal club info embedded in player responses — avoids circular import
class ClubMinimal(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    crest_url: str | None = None


class WorldTeamMinimal(BaseModel):
    """Minimal world-team info embedded in player responses."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    vendor_id: str  # API-Football team integer ID (as string)
    name: str
    crest_url: str | None = None
    country: str | None = None
    league_name: str | None = None


class WageFit(BaseModel):
    """B4: whether this player's wage fits the viewing club's remaining
    weekly wage room, and what would be left if signed. Uses Player.wage_weekly
    (a prospective figure — no contract exists yet) against ClubFinance's own
    wage_remaining_weekly, so this comparison rule lives in one place instead
    of being re-derived by hand on every page that needs a "fits wage room"
    check (Sessions 9/10)."""
    fits: bool
    wage_room_after: Decimal


class PlayerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    age: int | None
    nationality: str | None
    position: PlayerPosition | None
    status: PlayerStatus
    visibility: PlayerVisibility
    open_to_offers: bool
    photo_url: str | None
    team_name: str | None = None
    current_club: ClubMinimal | None = None
    world_team: WorldTeamMinimal | None = None
    # Bio fields (from vendor API)
    firstname: str | None = None
    lastname: str | None = None
    height: str | None = None
    weight: str | None = None
    birth_date: date | None = None
    birth_place: str | None = None
    birth_country: str | None = None
    created_at: datetime
    updated_at: datetime
    # TRA-66/73 enrichment fields
    market_value: Decimal | None = None
    market_value_currency: str | None = None
    valuation_low: Decimal | None = None
    valuation_high: Decimal | None = None
    valuation_source: ValuationSource | None = None
    valuation_as_of: date | None = None
    contract_expiry: date | None = None
    wage_weekly: Decimal | None = None
    wage_currency: str | None = None
    wage_source: WageSource | None = None
    wage_verified: bool = False
    # B4: populated only for authenticated club viewers with wage data to
    # compare against — see WageFit.
    wage_fit: WageFit | None = None


class ActiveDealStub(BaseModel):
    """Minimal deal info embedded in player responses to surface transfer state."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: str
    stage: str | None = None
    buyer_club: ClubMinimal | None = None
    seller_club: ClubMinimal | None = None
    agreed_fee: Decimal | None = None
    completed_at: datetime | None = None


class ActiveLoanStub(BaseModel):
    """Minimal loan info embedded in player detail.

    Public on purpose: a loan is public knowledge in football, and a club
    browsing the market needs it for a practical reason — during a loan
    `current_club` is the *loanee*, so an offer addressed there can never be
    accepted. `parent_club` is who actually owns him and who an approach must
    be sent to.
    """
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    end_date: date
    parent_club: ClubMinimal | None = None
    loanee_club: ClubMinimal | None = None


class PlayerDetailResponse(PlayerResponse):
    """Player detail — adds active contract, deal and loan state."""
    active_contract: ContractResponse | None = None
    active_deal: ActiveDealStub | None = None
    active_loan: ActiveLoanStub | None = None
    is_verified_player: bool = False


class PlayerTransferResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    transfer_date: date | None
    transfer_type: str | None
    team_in_vendor_id: str | None
    team_in_name: str | None
    team_in_crest_url: str | None
    team_out_vendor_id: str | None
    team_out_name: str | None
    team_out_crest_url: str | None
    fee_display: str | None


class PlayerInjuryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    league_name: str | None
    season: str | None
    fixture_date: date | None
    injury_type: str | None
    reason: str | None
    games_absent: int | None


class PlayerCreateRequest(BaseModel):
    name: str
    age: int | None = None
    nationality: str | None = None
    position: PlayerPosition | None = None
    visibility: PlayerVisibility = PlayerVisibility.PUBLIC
    open_to_offers: bool = False
    photo_url: str | None = None


class PlayerUpdateRequest(BaseModel):
    name: str | None = None
    age: int | None = None
    nationality: str | None = None
    position: PlayerPosition | None = None
    visibility: PlayerVisibility | None = None
    open_to_offers: bool | None = None
    photo_url: str | None = None
