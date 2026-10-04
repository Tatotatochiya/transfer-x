"""Lite L7: team contact (lite-mode BACKEND §6).

"Ask Sam about him" and "Send to Sam" pass a question to one colleague: the
staff member the club named as its Lite contact on the Team page, or else
the first sporting director or manager who isn't the person asking. With
nobody to name, the buttons read "your team" and the question goes to
everyone who can act on the market (owner, sporting directors, managers).

Questions are LITE_QUESTION notifications linking to what they're about.
They don't use the offer or agent message tables, which are between clubs.
"""
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.models import User
from app.clubs.capabilities import ROLE_CAPABILITIES, Capability
from app.clubs.models import ClubStaff, StaffRole

SUBJECT_LINKS = {
    "player": "/players/market/{id}",
    "offer": "/offers/{id}",
    "deal": "/deals/{id}",
}


def _first_name(user: User) -> str:
    if user.first_name:
        return user.first_name
    return user.email.split("@")[0].replace(".", " ").title()


async def team_contact(db: AsyncSession, club, asker: User) -> dict | None:
    """Who "Ask {name}" goes to, or None for "your team"."""
    staff = (await db.execute(
        select(ClubStaff).where(ClubStaff.club_id == club.id).options(selectinload(ClubStaff.user))
        .order_by(ClubStaff.created_at)
    )).scalars().all()
    others = [s for s in staff if s.user is not None and s.user.is_active and s.user_id != asker.id]
    named = next((s for s in others if s.is_lite_contact), None)
    if named is None:
        named = next((s for s in others if s.role in (StaffRole.SPORTING_DIRECTOR, StaffRole.MANAGER)), None)
    if named is None:
        return None
    return {"user_id": named.user_id, "name": _first_name(named.user), "full_name": named.user.display_label,
            "chosen": named.is_lite_contact}


async def _market_people(db: AsyncSession, club, asker: User) -> list[uuid.UUID]:
    """Everyone at the club who can act on the market, except the asker."""
    from app.auth.models import User as U

    ids = [club.user_id]
    staff = (await db.execute(select(ClubStaff).where(ClubStaff.club_id == club.id))).scalars().all()
    ids += [s.user_id for s in staff if Capability.MARKET_WRITE in ROLE_CAPABILITIES.get(s.role.value, frozenset())]
    active = {u for u in (await db.execute(select(U.id).where(U.id.in_(ids), U.is_active.is_(True)))).scalars()}
    return [i for i in dict.fromkeys(ids) if i in active and i != asker.id]


async def ask_team(
    db: AsyncSession, club, asker: User, *, subject_type: str, subject_id: uuid.UUID | None, text: str,
) -> dict:
    from app.audit import service as audit_service
    from app.notifications import service as notif_service
    from app.notifications.models import NotificationType

    text = text.strip()
    if not text:
        raise ValueError("Write your question first")
    related_player_id = None
    link = "/dashboard"
    if subject_type != "general":
        if subject_id is None or subject_type not in SUBJECT_LINKS:
            raise ValueError("Say what the question is about")
        related_player_id = await _check_subject(db, club, subject_type, subject_id)
        link = SUBJECT_LINKS[subject_type].format(id=subject_id)

    contact = await team_contact(db, club, asker)
    recipients = [contact["user_id"]] if contact else await _market_people(db, club, asker)
    if not recipients:
        raise ValueError("There's nobody else at your club to ask yet. Invite your team from the Team page.")
    asker_name = asker.full_name or _first_name(asker)
    for uid in recipients:
        await notif_service.create_notification(
            db, recipient_user_id=uid, type=NotificationType.LITE_QUESTION,
            message=f"{asker_name} asks: {text[:300]}", link=link, related_player_id=related_player_id,
            title=f"{asker_name} asks", body=text[:120],
        )
    await audit_service.emit(
        db, entity_type="CLUB", entity_id=club.id, action="LITE_QUESTION_ASKED", actor_user_id=asker.id,
        payload={"subject_type": subject_type, "subject_id": str(subject_id) if subject_id else None,
                 "recipients": [str(r) for r in recipients]},
        description=f"Asked {contact['full_name'] if contact else 'the team'} a question",
    )
    return {"sent_to": contact["name"] if contact else "your team", "recipients": len(recipients)}


async def _check_subject(db: AsyncSession, club, subject_type: str, subject_id: uuid.UUID):
    """The subject must be one this club can see. Returns its player id."""
    if subject_type == "player":
        from app.players.models import Player

        player = await db.get(Player, subject_id)
        if player is None:
            raise LookupError("Player not found")
        return player.id
    if subject_type == "offer":
        from app.offers.models import Offer

        offer = await db.get(Offer, subject_id)
        if offer is None or str(club.id) not in {str(offer.from_club_id), str(offer.to_club_id)}:
            raise LookupError("Offer not found")
        return offer.player_id
    from app.deals.models import Deal

    deal = await db.get(Deal, subject_id)
    if deal is None or str(club.id) not in {str(deal.buyer_club_id), str(deal.seller_club_id)}:
        raise LookupError("Deal not found")
    return deal.player_id
