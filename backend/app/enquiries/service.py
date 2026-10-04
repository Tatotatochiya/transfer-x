"""Enquiries: the rules. See models.py for why they exist."""
import uuid

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.audit import service as audit_service
from app.common.schemas import WhoseMove
from app.enquiries.models import Enquiry, EnquiryMessage, EnquiryStatus
from app.enquiries.schemas import EnquiryMessageResponse, EnquiryParty, EnquiryResponse
from app.notifications.models import NotificationType


def _options():
    return [
        selectinload(Enquiry.player),
        selectinload(Enquiry.from_club),
        selectinload(Enquiry.to_club),
        selectinload(Enquiry.messages),
    ]


async def get_enquiry(db: AsyncSession, enquiry_id: uuid.UUID) -> Enquiry | None:
    return (await db.execute(
        select(Enquiry).where(Enquiry.id == enquiry_id).options(*_options())
    )).scalar_one_or_none()


def _require_party(enquiry: Enquiry, club_id: uuid.UUID) -> None:
    if club_id not in (enquiry.from_club_id, enquiry.to_club_id):
        # Callers turn this into a 404: whether an enquiry exists is not a
        # third club's business.
        raise LookupError("Enquiry not found")


def whose_move(enquiry: Enquiry, viewer_club_id: uuid.UUID) -> WhoseMove:
    if enquiry.status != EnquiryStatus.OPEN:
        return WhoseMove.NEITHER
    return WhoseMove.THEIR if enquiry.last_actor_club_id == viewer_club_id else WhoseMove.YOUR


def to_response(enquiry: Enquiry, viewer_club_id: uuid.UUID, *, with_messages: bool) -> EnquiryResponse:
    """Build the response for one side. The asking club is masked from the
    owning club when anonymous — its id as well as its name, since the id
    resolves via GET /clubs/{id} (the lesson of ADR 0004)."""
    asking_view = viewer_club_id == enquiry.from_club_id
    if enquiry.is_anonymous and not asking_view:
        league = enquiry.from_club.masking_league if enquiry.from_club else None
        asking = EnquiryParty(id=None, name=f"A {league} club" if league else "An undisclosed club")
    else:
        asking = EnquiryParty(id=enquiry.from_club_id, name=enquiry.from_club.name if enquiry.from_club else "",
                              crest_url=enquiry.from_club.crest_url if enquiry.from_club else None)
    owning = EnquiryParty(id=enquiry.to_club_id, name=enquiry.to_club.name if enquiry.to_club else "",
                          crest_url=enquiry.to_club.crest_url if enquiry.to_club else None)
    messages = enquiry.messages or []
    return EnquiryResponse(
        id=enquiry.id,
        player_id=enquiry.player_id,
        player_name=enquiry.player.name if enquiry.player else None,
        player_photo_url=enquiry.player.photo_url if enquiry.player else None,
        status=enquiry.status,
        is_anonymous=enquiry.is_anonymous,
        asking_club=asking,
        owning_club=owning,
        role="asking" if asking_view else "owning",
        whose_move=whose_move(enquiry, viewer_club_id),
        created_at=enquiry.created_at,
        updated_at=enquiry.updated_at,
        last_message=messages[-1].body[:160] if messages else None,
        messages=[
            EnquiryMessageResponse(
                id=m.id, body=m.body, created_at=m.created_at,
                side="mine" if m.sender_club_id == viewer_club_id else "theirs",
            )
            for m in messages
        ] if with_messages else [],
    )


async def _notify(db: AsyncSession, enquiry: Enquiry, *, to_club_id: uuid.UUID, message: str, type) -> None:
    from app.notifications.service import notify_club

    await notify_club(
        db, to_club_id, type=type, message=message,
        link=f"/enquiries/{enquiry.id}", related_player_id=enquiry.player_id,
    )


async def create_enquiry(
    db: AsyncSession, *, player_id: uuid.UUID, from_club_id: uuid.UUID, body: str, is_anonymous: bool,
    actor_user_id: uuid.UUID | None = None,
) -> Enquiry:
    """Ask the club that owns a player about him. Refused for a player at a
    club outside TransferX (no one could answer), a free agent (sign him
    instead), your own player, or when you already have an open enquiry
    about him (the existing one is returned in the error)."""
    from app.players import service as players_service
    from app.players.models import PlayerStatus

    player = await players_service.get_player_by_id(db, player_id)
    if player is None:
        raise ValueError("Player not found")
    owner = await players_service.get_owning_club_id(db, player)
    if owner is None:
        if player.status == PlayerStatus.FREE_AGENT:
            raise ValueError("He is a free agent — sign him from his page rather than enquiring")
        raise ValueError("He plays for a club that is not on TransferX, so no one could answer an enquiry")
    if owner == from_club_id:
        raise ValueError("He is your own player")
    existing = (await db.execute(
        select(Enquiry).where(
            Enquiry.player_id == player_id,
            Enquiry.from_club_id == from_club_id,
            Enquiry.status == EnquiryStatus.OPEN,
        )
    )).scalars().first()
    if existing is not None:
        raise FileExistsError(str(existing.id))

    enquiry = Enquiry(
        player_id=player_id, from_club_id=from_club_id, to_club_id=owner,
        is_anonymous=is_anonymous, last_actor_club_id=from_club_id,
    )
    db.add(enquiry)
    await db.flush()
    db.add(EnquiryMessage(enquiry_id=enquiry.id, sender_club_id=from_club_id, body=body.strip()))
    await db.flush()
    await audit_service.emit(
        db, entity_type="ENQUIRY", entity_id=enquiry.id, action="ENQUIRY_CREATED",
        actor_user_id=actor_user_id, payload={"player_id": str(player_id), "anonymous": is_anonymous},
        description="Enquiry sent",
    )
    await _notify(
        db, enquiry, to_club_id=owner, type=NotificationType.ENQUIRY_RECEIVED,
        message=f"An enquiry about {player.name}",
    )
    return enquiry


async def add_message(
    db: AsyncSession, enquiry: Enquiry, *, sender_club_id: uuid.UUID, body: str,
    actor_user_id: uuid.UUID | None = None,
) -> Enquiry:
    _require_party(enquiry, sender_club_id)
    if enquiry.status != EnquiryStatus.OPEN:
        raise ValueError("This enquiry is closed")
    db.add(EnquiryMessage(enquiry_id=enquiry.id, sender_club_id=sender_club_id, body=body.strip()))
    enquiry.last_actor_club_id = sender_club_id
    await db.flush()
    other = enquiry.to_club_id if sender_club_id == enquiry.from_club_id else enquiry.from_club_id
    player = enquiry.player.name if enquiry.player else "the player"
    await _notify(
        db, enquiry, to_club_id=other, type=NotificationType.ENQUIRY_REPLIED,
        message=f"A reply about {player}",
    )
    await audit_service.emit(
        db, entity_type="ENQUIRY", entity_id=enquiry.id, action="ENQUIRY_MESSAGE",
        actor_user_id=actor_user_id, description="Enquiry message",
    )
    return enquiry


async def close_enquiry(
    db: AsyncSession, enquiry: Enquiry, *, club_id: uuid.UUID, actor_user_id: uuid.UUID | None = None,
) -> Enquiry:
    _require_party(enquiry, club_id)
    if enquiry.status == EnquiryStatus.CLOSED:
        raise ValueError("This enquiry is already closed")
    enquiry.status = EnquiryStatus.CLOSED
    await db.flush()
    await audit_service.emit(
        db, entity_type="ENQUIRY", entity_id=enquiry.id, action="ENQUIRY_CLOSED",
        actor_user_id=actor_user_id, description="Enquiry closed",
    )
    return enquiry


async def list_enquiries(db: AsyncSession, club_id: uuid.UUID, *, box: str | None = None) -> list[Enquiry]:
    q = select(Enquiry).options(*_options())
    if box == "received":
        q = q.where(Enquiry.to_club_id == club_id)
    elif box == "sent":
        q = q.where(Enquiry.from_club_id == club_id)
    else:
        q = q.where(or_(Enquiry.to_club_id == club_id, Enquiry.from_club_id == club_id))
    return list((await db.execute(q.order_by(Enquiry.updated_at.desc()).limit(200))).scalars())
