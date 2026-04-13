from datetime import datetime
from pydantic import BaseModel, ConfigDict


class FixtureResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    fixture_vendor_id: int
    league_id: int | None
    league_name: str | None
    round: str | None
    home_team_vendor_id: int
    home_team_name: str
    home_team_crest_url: str | None
    away_team_vendor_id: int
    away_team_name: str
    away_team_crest_url: str | None
    kickoff_at: datetime | None
    status_short: str
    status_long: str | None
    home_goals: int | None
    away_goals: int | None
    venue_name: str | None
