"""Live updates for a deal: tell every open page that something changed."""
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


async def deal_updated(db: AsyncSession, deal_id: uuid.UUID) -> None:
    """Push DEAL_UPDATED to everyone on the deal: both clubs' members, the
    player's agent and the player. Their pages refetch the deal, its
    negotiation and its rounds (frontend hooks/useWebSocket.ts). Call after
    the change is committed."""
    from app.agents.models import AgentDealInvitation
    from app.auth.models import AgentProfile, PlayerProfile
    from app.deals.service import get_deal_by_id
    from app.notifications.service import club_member_user_ids
    from app.ws.manager import manager

    deal = await get_deal_by_id(db, deal_id)
    if deal is None:
        return
    user_ids: set[uuid.UUID] = set()
    for club_id in (deal.buyer_club_id, deal.seller_club_id):
        if club_id is not None:
            user_ids.update(await club_member_user_ids(db, club_id))
    agent_ids = {deal.commission_agent_id} if deal.commission_agent_id else set()
    agent_ids.update((await db.execute(select(AgentDealInvitation.agent_id).where(
        AgentDealInvitation.deal_id == deal.id))).scalars())
    if agent_ids:
        user_ids.update((await db.execute(select(AgentProfile.user_id).where(
            AgentProfile.id.in_(agent_ids)))).scalars())
    user_ids.update((await db.execute(select(PlayerProfile.user_id).where(
        PlayerProfile.player_id == deal.player_id, PlayerProfile.user_id.is_not(None)))).scalars())
    await manager.broadcast_to_users(list(user_ids), {"type": "DEAL_UPDATED", "id": str(deal.id)})
