import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy import update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession

from app.mandates.models import Mandate, MandateStatus
from app.players.models import Contract, Player


async def create_mandate(
    db: AsyncSession,
    agent_profile_id: uuid.UUID,
    player_id: uuid.UUID,
    exclusive: bool,
    start_date: date | None = None,
    end_date: date | None = None,
    territory: str | None = None,
) -> Mandate:
    # Prevent duplicate active mandates for the same agent+player (double-submit, re-import).
    existing = await db.execute(
        select(Mandate).where(
            Mandate.agent_id == agent_profile_id,
            Mandate.player_id == player_id,
            Mandate.status == MandateStatus.ACTIVE,
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise ValueError("You already represent this player")

    if exclusive:
        result = await db.execute(
            select(Mandate).where(
                Mandate.player_id == player_id,
                Mandate.exclusive.is_(True),
                Mandate.status == MandateStatus.ACTIVE,
            )
        )
        if result.scalar_one_or_none() is not None:
            raise ValueError("Player already has an active exclusive mandate")

    mandate = Mandate(
        agent_id=agent_profile_id,
        player_id=player_id,
        exclusive=exclusive,
        start_date=start_date,
        end_date=end_date,
        territory=territory,
    )
    db.add(mandate)
    await db.flush()

    if exclusive:
        await db.execute(
            sa_update(Player)
            .where(Player.id == player_id)
            .values(agent_id=agent_profile_id)
        )

    return mandate


async def revoke_mandate_as_player(
    db: AsyncSession,
    mandate_id: uuid.UUID,
    player_id: uuid.UUID,
) -> Mandate:
    mandate = await db.get(Mandate, mandate_id)
    if mandate is None:
        raise ValueError("Mandate not found")
    if mandate.player_id != player_id:
        raise ValueError("Not your mandate")
    if mandate.status != MandateStatus.ACTIVE:
        raise ValueError("Mandate is not active")

    mandate.status = MandateStatus.REVOKED
    await db.flush()

    if mandate.exclusive:
        await db.execute(
            sa_update(Player)
            .where(Player.id == player_id, Player.agent_id == mandate.agent_id)
            .values(agent_id=None)
        )

    return mandate


async def get_mandate_detail(
    db: AsyncSession,
    mandate_id: uuid.UUID,
    agent_profile_id: uuid.UUID,
) -> tuple[Mandate, Player, Contract | None]:
    from sqlalchemy.orm import selectinload

    result = await db.execute(
        select(Mandate, Player)
        .join(Player, Player.id == Mandate.player_id)
        .options(selectinload(Player.current_club))
        .where(Mandate.id == mandate_id, Mandate.agent_id == agent_profile_id)
    )
    row = result.one_or_none()
    if row is None:
        raise ValueError("Mandate not found")
    mandate, player = row

    contract_result = await db.execute(
        select(Contract)
        .where(Contract.player_id == player.id, Contract.is_active.is_(True))
        .order_by(Contract.end_date.desc().nullslast())
        .limit(1)
    )
    contract = contract_result.scalar_one_or_none()
    return mandate, player, contract


async def patch_mandate(
    db: AsyncSession,
    mandate_id: uuid.UUID,
    agent_profile_id: uuid.UUID,
    updates: dict,
) -> Mandate:
    mandate = await db.get(Mandate, mandate_id)
    if mandate is None or mandate.agent_id != agent_profile_id:
        raise ValueError("Mandate not found")
    for k, v in updates.items():
        setattr(mandate, k, v)
    await db.flush()
    return mandate


async def revoke_mandate(
    db: AsyncSession,
    mandate_id: uuid.UUID,
    agent_profile_id: uuid.UUID,
) -> Mandate:
    mandate = await db.get(Mandate, mandate_id)
    if mandate is None:
        raise ValueError("Mandate not found")
    if mandate.agent_id != agent_profile_id:
        raise ValueError("Not your mandate")
    if mandate.status != MandateStatus.ACTIVE:
        raise ValueError("Mandate is not active")

    mandate.status = MandateStatus.REVOKED
    await db.flush()

    if mandate.exclusive:
        await db.execute(
            sa_update(Player)
            .where(Player.id == mandate.player_id, Player.agent_id == agent_profile_id)
            .values(agent_id=None)
        )

    return mandate
