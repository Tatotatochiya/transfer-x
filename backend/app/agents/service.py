import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import AgentProfile
from app.mandates.models import Mandate, MandateStatus
from app.players.models import Player


async def update_profile(db: AsyncSession, profile: AgentProfile, **kwargs) -> AgentProfile:
    for k, v in kwargs.items():
        setattr(profile, k, v)
    await db.flush()
    return profile


async def list_represented_players(
    db: AsyncSession, agent_profile_id: uuid.UUID
) -> list[tuple[Mandate, Player]]:
    result = await db.execute(
        select(Mandate, Player)
        .join(Player, Player.id == Mandate.player_id)
        .where(
            Mandate.agent_id == agent_profile_id,
            Mandate.status == MandateStatus.ACTIVE,
        )
        .order_by(Player.name)
    )
    return result.all()
