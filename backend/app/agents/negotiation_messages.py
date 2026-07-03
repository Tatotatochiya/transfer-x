"""TRA-136 — scoped negotiation messaging (agent<->club, agent<->player threads).

Visibility is enforced here, server-side, and nowhere else:
  - The mandated agent may read/write both CLUB_SIDE and PLAYER_SIDE.
  - A club that is a party to the deal (buyer or seller — mirrors the existing
    `_require_party` rule used for `club_respond_to_negotiation`) may
    read/write only CLUB_SIDE.
  - The player linked to the deal may read/write only PLAYER_SIDE.
Never trust a `thread` query/body param alone — always intersect with the
caller's allowed set.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.agents.models import AgentNegotiation, NegotiationMessage, NegotiationThread
from app.auth.models import User, UserType
from app.deals.models import Deal


async def get_negotiation_with_deal(
    db: AsyncSession, negotiation_id: uuid.UUID
) -> tuple[AgentNegotiation, Deal] | None:
    result = await db.execute(
        select(AgentNegotiation)
        .where(AgentNegotiation.id == negotiation_id)
        .options(selectinload(AgentNegotiation.deal))
    )
    neg = result.scalar_one_or_none()
    if neg is None:
        return None
    return neg, neg.deal


async def resolve_allowed_threads(
    db: AsyncSession, negotiation: AgentNegotiation, deal: Deal, current_user: User
) -> set[NegotiationThread]:
    if current_user.is_superuser:
        return {NegotiationThread.CLUB_SIDE, NegotiationThread.PLAYER_SIDE}

    if current_user.user_type == UserType.AGENT:
        from app.auth.models import AgentProfile
        result = await db.execute(select(AgentProfile).where(AgentProfile.user_id == current_user.id))
        profile = result.scalar_one_or_none()
        if profile is not None and profile.id == negotiation.agent_id:
            return {NegotiationThread.CLUB_SIDE, NegotiationThread.PLAYER_SIDE}
        return set()

    if current_user.user_type == UserType.CLUB:
        from app.clubs import service as clubs_service
        club = await clubs_service.get_club_by_user_id(db, current_user.id)
        parties = {deal.buyer_club_id}
        if deal.seller_club_id:
            parties.add(deal.seller_club_id)
        if club is not None and club.id in parties:
            return {NegotiationThread.CLUB_SIDE}
        return set()

    if current_user.user_type == UserType.PLAYER:
        from app.auth.models import PlayerProfile
        result = await db.execute(select(PlayerProfile).where(PlayerProfile.user_id == current_user.id))
        pp = result.scalar_one_or_none()
        if pp is not None and pp.player_id == deal.player_id:
            return {NegotiationThread.PLAYER_SIDE}
        return set()

    return set()


async def list_messages(
    db: AsyncSession, negotiation_id: uuid.UUID, threads: set[NegotiationThread]
) -> list[NegotiationMessage]:
    if not threads:
        return []
    result = await db.execute(
        select(NegotiationMessage)
        .where(
            NegotiationMessage.negotiation_id == negotiation_id,
            NegotiationMessage.thread.in_(threads),
        )
        .order_by(NegotiationMessage.created_at.asc())
    )
    return list(result.scalars())


async def create_message(
    db: AsyncSession,
    *,
    negotiation_id: uuid.UUID,
    thread: NegotiationThread,
    sender_user_id: uuid.UUID,
    body: str,
) -> NegotiationMessage:
    msg = NegotiationMessage(
        negotiation_id=negotiation_id,
        thread=thread,
        sender_user_id=sender_user_id,
        body=body,
    )
    db.add(msg)
    await db.flush()
    return msg


async def sender_label(db: AsyncSession, current_user: User) -> str:
    """Human-readable label for the UI — e.g. 'Agent', 'Club — Arsenal', 'Player'."""
    if current_user.user_type == UserType.AGENT:
        from app.auth.models import AgentProfile
        result = await db.execute(select(AgentProfile).where(AgentProfile.user_id == current_user.id))
        agent = result.scalar_one_or_none()
        return f"Agent — {agent.display_name}" if agent else "Agent"
    if current_user.user_type == UserType.CLUB:
        from app.clubs import service as clubs_service
        club = await clubs_service.get_club_by_user_id(db, current_user.id)
        return f"Club — {club.name}" if club else "Club"
    if current_user.user_type == UserType.PLAYER:
        return "Player"
    return "Staff"


async def notify_counterparty(
    db: AsyncSession,
    *,
    negotiation: AgentNegotiation,
    deal: Deal,
    thread: NegotiationThread,
    sender: User,
) -> None:
    """TRA-136: notify whoever is on 'the other end' of this thread."""
    from app.notifications import service as notif_service
    from app.notifications.models import NotificationType

    link = f"/deals/{deal.id}"
    message = "New message in your negotiation"

    if sender.user_type == UserType.AGENT:
        if thread == NegotiationThread.CLUB_SIDE:
            from app.clubs import service as clubs_service
            for club_id in {deal.buyer_club_id, deal.seller_club_id} - {None}:
                club = await clubs_service.get_club_by_id(db, uuid.UUID(str(club_id)))
                if club:
                    await notif_service.create_notification(
                        db, recipient_user_id=club.user_id,
                        type=NotificationType.NEGOTIATION_MESSAGE, message=message, link=link,
                        related_player_id=deal.player_id,
                    )
        else:
            from app.auth.models import PlayerProfile
            result = await db.execute(select(PlayerProfile).where(PlayerProfile.player_id == deal.player_id))
            pp = result.scalar_one_or_none()
            if pp is not None:
                await notif_service.create_notification(
                    db, recipient_user_id=pp.user_id,
                    type=NotificationType.NEGOTIATION_MESSAGE, message=message, link="/player/profile",
                    related_player_id=deal.player_id,
                )
        return

    # Club or player sent it — the agent is always the other party
    from app.auth.models import AgentProfile
    result = await db.execute(select(AgentProfile).where(AgentProfile.id == negotiation.agent_id))
    agent = result.scalar_one_or_none()
    if agent is not None:
        await notif_service.create_notification(
            db, recipient_user_id=agent.user_id,
            type=NotificationType.NEGOTIATION_MESSAGE, message=message, link=link,
            related_player_id=deal.player_id,
        )
