"""Check your squad (Phase 1): a club confirms each player's contract, wage
and valuation, and sees what's missing.

A squad player is one the club holds: an active contract with the club,
`current_club_id` set to it (players placed by TransferX staff can arrive
without a contract row), or a player the club added itself who has no club
yet (players/service.get_owning_club_id's fallback). A player without a contract, end date or wage can't
be sold or valued properly, so those are flagged first; a missing valuation
is flagged but optional.
"""
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import and_, false, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.players.models import Contract, Player

# The order the page lists them in, worst first.
NO_CONTRACT = "NO_CONTRACT"
ENDED = "ENDED"
NO_END_DATE = "NO_END_DATE"
NO_WAGE = "NO_WAGE"
NO_VALUATION = "NO_VALUATION"
BLOCKING = {NO_CONTRACT, ENDED, NO_END_DATE, NO_WAGE}
ORDER = [NO_CONTRACT, ENDED, NO_END_DATE, NO_WAGE, NO_VALUATION]


def _active_with(player: Player, club_id: uuid.UUID) -> Contract | None:
    return next((c for c in player.contracts if c.is_active and str(c.club_id) == str(club_id)), None)


def issues_for(player: Player, club_id: uuid.UUID, today: date | None = None) -> list[str]:
    today = today or date.today()
    c = _active_with(player, club_id)
    if c is None:
        return [NO_CONTRACT]
    found = []
    if c.end_date is None:
        found.append(NO_END_DATE)
    elif c.end_date < today:
        found.append(ENDED)
    if c.wage_weekly is None:
        found.append(NO_WAGE)
    if c.club_valuation is None:
        found.append(NO_VALUATION)
    return sorted(found, key=ORDER.index)


async def _owner_id(db: AsyncSession, club_id: uuid.UUID) -> uuid.UUID | None:
    from app.clubs.models import Club

    return (await db.execute(select(Club.user_id).where(Club.id == club_id))).scalar_one_or_none()


def _added_by_club(player: Player, owner_id: uuid.UUID | None) -> bool:
    return (player.current_club_id is None and owner_id is not None
            and player.created_by_user_id is not None and str(player.created_by_user_id) == str(owner_id))


async def squad(db: AsyncSession, club_id: uuid.UUID) -> list[Player]:
    held = select(Contract.player_id).where(Contract.club_id == club_id, Contract.is_active.is_(True))
    owner_id = await _owner_id(db, club_id)
    added = and_(Player.current_club_id.is_(None), Player.created_by_user_id == owner_id) if owner_id else false()
    rows = await db.execute(
        select(Player)
        .where(or_(Player.current_club_id == club_id, Player.id.in_(held), added))
        .options(selectinload(Player.contracts))
        .order_by(Player.name)
        # Fresh contracts even when this session already loaded the players
        # (confirm() just changed one).
        .execution_options(populate_existing=True)
    )
    return list(rows.scalars().unique())


async def check(db: AsyncSession, club_id: uuid.UUID) -> dict:
    from app.auth.models import User

    players = await squad(db, club_id)
    confirmer_ids = {c.confirmed_by_user_id for p in players if (c := _active_with(p, club_id)) and c.confirmed_by_user_id}
    names = {}
    if confirmer_ids:
        for u in (await db.execute(select(User).where(User.id.in_(confirmer_ids)))).scalars():
            names[u.id] = u.display_label
    items = []
    for p in players:
        c = _active_with(p, club_id)
        found = issues_for(p, club_id)
        items.append({
            "player_id": p.id,
            "name": p.name,
            "position": getattr(p.position, "value", p.position),
            "contract": None if c is None else {
                "start_date": c.start_date, "end_date": c.end_date, "wage_weekly": c.wage_weekly,
                "club_valuation": c.club_valuation, "confirmed_at": c.confirmed_at,
                "confirmed_by": names.get(c.confirmed_by_user_id),
            },
            "issues": found,
            "confirmed": c is not None and c.confirmed_at is not None and not (set(found) & BLOCKING),
        })
    items.sort(key=lambda i: (i["confirmed"], min((ORDER.index(x) for x in i["issues"]), default=len(ORDER)), i["name"]))
    return {
        "players": items,
        "total": len(items),
        "confirmed": sum(i["confirmed"] for i in items),
        "without_contract": sum(NO_CONTRACT in i["issues"] for i in items),
        "needs_attention": sum(bool(set(i["issues"]) & BLOCKING) for i in items),
    }


async def confirm(
    db: AsyncSession, club_id: uuid.UUID, player_id: uuid.UUID, user_id: uuid.UUID, *,
    start_date: date | None, end_date: date, wage_weekly: Decimal, club_valuation: Decimal | None,
) -> tuple[Contract, dict]:
    """Create or correct the player's contract with the club and mark it
    confirmed. Returns the contract and what changed, for the audit trail."""
    from app.players import service as players_service

    player = (await db.execute(
        select(Player).where(Player.id == player_id).options(selectinload(Player.contracts))
    )).scalar_one_or_none()
    if player is None:
        raise LookupError("Player not found")
    contract = _active_with(player, club_id)
    if contract is None:
        in_squad = player.current_club_id is not None and str(player.current_club_id) == str(club_id)
        if not in_squad and not _added_by_club(player, await _owner_id(db, club_id)):
            raise PermissionError("He isn't in your squad")
        if any(c.is_active for c in player.contracts):
            raise ValueError("His active contract is with another club. Contact TransferX to correct it.")
    if end_date < date.today():
        raise ValueError("The contract end date is in the past")
    if start_date and start_date > end_date:
        raise ValueError("The contract starts after it ends")

    changes: dict = {}
    if contract is None:
        contract = await players_service.create_contract(
            db, player, club_id, start_date=start_date, end_date=end_date, wage_weekly=wage_weekly,
        )
        changes["contract"] = "created"
    for field, value in (("start_date", start_date), ("end_date", end_date),
                         ("wage_weekly", wage_weekly), ("club_valuation", club_valuation)):
        if field == "start_date" and value is None:
            continue
        old = getattr(contract, field)
        if old != value:
            changes[field] = {"from": str(old) if old is not None else None, "to": str(value) if value is not None else None}
            setattr(contract, field, value)
    contract.confirmed_at = datetime.now(timezone.utc)
    contract.confirmed_by_user_id = user_id
    await db.flush()
    return contract, changes
