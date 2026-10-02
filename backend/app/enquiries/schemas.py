import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.common.schemas import WhoseMove
from app.enquiries.models import EnquiryStatus


class EnquiryCreateRequest(BaseModel):
    player_id: uuid.UUID
    body: str = Field(min_length=1, max_length=2000)
    is_anonymous: bool = False


class EnquiryMessageRequest(BaseModel):
    body: str = Field(min_length=1, max_length=2000)


class EnquiryParty(BaseModel):
    """A club in an enquiry. `id` is null and `name` is "A {league} club" when
    the asking club is anonymous and the viewer is the owning club."""
    id: uuid.UUID | None
    name: str
    # Null when masked, as the id is.
    crest_url: str | None = None


class EnquiryMessageResponse(BaseModel):
    id: uuid.UUID
    body: str
    created_at: datetime
    # "mine" or "theirs" rather than a club id — an id would unmask an
    # anonymous asker.
    side: str


class EnquiryResponse(BaseModel):
    id: uuid.UUID
    player_id: uuid.UUID
    player_name: str | None
    status: EnquiryStatus
    is_anonymous: bool
    asking_club: EnquiryParty
    owning_club: EnquiryParty
    # Which side the viewer is on: "asking" or "owning".
    role: str
    whose_move: WhoseMove
    created_at: datetime
    updated_at: datetime
    last_message: str | None = None
    messages: list[EnquiryMessageResponse] = []
