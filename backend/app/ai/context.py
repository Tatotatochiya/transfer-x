"""DB context assemblers — builds serialisable dicts for LLM prompts."""
from __future__ import annotations

import uuid
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload


async def build_squad_context(db: AsyncSession, club_id: uuid.UUID) -> dict:
    """Assemble club + active squad data for LLM context."""
    from app.clubs.models import Club
    from app.players.models import Contract, Player
    from app.stats.models import PlayerForm

    club = await db.get(Club, club_id, options=[selectinload(Club.finance)])
    if not club:
        return {}

    # Primary source: all players whose current_club_id matches this club.
    # Left-join active contracts so wage/expiry data is included when it exists.
    players_result = await db.execute(
        select(Player).where(Player.current_club_id == club_id)
    )
    players = players_result.scalars().all()

    player_ids = [p.id for p in players]

    # Active contracts indexed by player_id (most have none — that's fine).
    contracts_result = await db.execute(
        select(Contract).where(
            Contract.player_id.in_(player_ids),
            Contract.is_active == True,  # noqa: E712
        )
    )
    contract_by_player: dict[uuid.UUID, Contract] = {
        c.player_id: c for c in contracts_result.scalars().all()
    }

    forms_result = await db.execute(
        select(PlayerForm).where(PlayerForm.player_id.in_(player_ids))
    )
    form_by_player: dict[uuid.UUID, PlayerForm] = {
        f.player_id: f for f in forms_result.scalars().all()
    }

    today = date.today()
    expiring_threshold = today + timedelta(days=180)

    squad = []
    for p in players:
        c = contract_by_player.get(p.id)
        form = form_by_player.get(p.id)
        squad.append({
            "name": p.name,
            "age": p.age,
            "position": p.position.value if p.position else None,
            "nationality": p.nationality,
            "wage_weekly": float(c.wage_weekly) if c and c.wage_weekly else None,
            "contract_end": c.end_date.isoformat() if c and c.end_date else None,
            "contract_expiring_soon": bool(
                c and c.end_date and c.end_date <= expiring_threshold
            ),
            "release_clause": float(c.release_clause) if c and c.release_clause else None,
            "club_valuation": float(c.club_valuation) if c and c.club_valuation else None,
            "form_score": float(form.form_score) if form else None,
            "open_to_offers": p.open_to_offers,
        })

    finance = club.finance
    return {
        "club_name": club.name,
        "country": club.country,
        "league": club.league_name,
        "transfer_budget_remaining": float(finance.transfer_remaining) if finance else None,
        "wage_budget_remaining_weekly": float(finance.wage_remaining_weekly) if finance else None,
        "squad": squad,
    }


async def build_player_context(db: AsyncSession, player_id: uuid.UUID) -> dict:
    """Assemble player stats/profile for LLM context."""
    from app.clubs.models import Club
    from app.players.models import Contract, Player
    from app.stats.models import PlayerForm, PlayerStats

    player = await db.get(Player, player_id)
    if not player:
        return {}

    current_club: Club | None = None
    if player.current_club_id:
        current_club = await db.get(Club, player.current_club_id)

    contract_result = await db.execute(
        select(Contract)
        .where(Contract.player_id == player_id, Contract.is_active == True)  # noqa: E712
        .limit(1)
    )
    contract = contract_result.scalar_one_or_none()

    stats_result = await db.execute(
        select(PlayerStats)
        .where(PlayerStats.player_id == player_id)
        .order_by(PlayerStats.updated_at.desc())
        .limit(1)
    )
    stats = stats_result.scalar_one_or_none()

    form_result = await db.execute(
        select(PlayerForm).where(PlayerForm.player_id == player_id)
    )
    form = form_result.scalar_one_or_none()

    stats_dict: dict = {}
    if stats:
        candidates = {
            "goals": stats.goals,
            "assists": stats.assists,
            "appearances": stats.appearances,
            "avg_rating": float(stats.avg_rating) if stats.avg_rating else None,
            "minutes": stats.minutes,
            "key_passes": stats.key_passes,
            "pass_accuracy": stats.pass_accuracy,
            "tackles_total": stats.tackles_total,
            "interceptions": stats.interceptions,
            "dribbles_success": stats.dribbles_success,
            "saves": stats.saves,
            "yellow_cards": stats.yellow_cards,
            "red_cards": stats.red_cards,
        }
        stats_dict = {k: v for k, v in candidates.items() if v is not None}

    return {
        "name": player.name,
        "age": player.age,
        "position": player.position.value if player.position else None,
        "nationality": player.nationality,
        "current_club": current_club.name if current_club else None,
        "current_club_league": current_club.league_name if current_club else None,
        "status": player.status.value if player.status else None,
        "height": player.height,
        "weight": player.weight,
        "contract_end": contract.end_date.isoformat() if contract and contract.end_date else None,
        "wage_weekly": float(contract.wage_weekly) if contract and contract.wage_weekly else None,
        "release_clause": float(contract.release_clause) if contract and contract.release_clause else None,
        "club_valuation": float(contract.club_valuation) if contract and contract.club_valuation else None,
        "form_score": float(form.form_score) if form else None,
        "form_trend": float(form.trend) if form and form.trend else None,
        "stats": stats_dict,
    }


async def build_shortlist_context(
    db: AsyncSession,
    shortlist_id: uuid.UUID,
) -> dict:
    """Assemble shortlist items with player data and form scores for LLM context."""
    from app.players.models import Player
    from app.scouting.models import Shortlist, ShortlistItem
    from app.stats.models import PlayerForm, PlayerStats

    shortlist = await db.get(Shortlist, shortlist_id)
    if not shortlist:
        return {}

    items_result = await db.execute(
        select(ShortlistItem)
        .where(ShortlistItem.shortlist_id == shortlist_id)
        .options(selectinload(ShortlistItem.player))
        .order_by(ShortlistItem.priority)
    )
    items = items_result.scalars().all()

    player_ids = [i.player_id for i in items if i.player_id]

    forms_result = await db.execute(
        select(PlayerForm).where(PlayerForm.player_id.in_(player_ids))
    )
    form_by_player = {f.player_id: f for f in forms_result.scalars().all()}

    stats_result = await db.execute(
        select(PlayerStats)
        .where(PlayerStats.player_id.in_(player_ids))
        .order_by(PlayerStats.updated_at.desc())
    )
    stats_by_player: dict[uuid.UUID, PlayerStats] = {}
    for s in stats_result.scalars().all():
        if s.player_id not in stats_by_player:
            stats_by_player[s.player_id] = s

    shortlist_items = []
    for item in items:
        p = item.player
        if not p:
            continue
        form = form_by_player.get(p.id)
        stats = stats_by_player.get(p.id)

        entry: dict = {
            "player_id": str(p.id),
            "name": p.name,
            "age": p.age,
            "position": p.position.value if p.position else None,
            "nationality": p.nationality,
            "user_priority": item.priority,
            "notes": item.notes,
            "form_score": float(form.form_score) if form else None,
        }
        if stats:
            entry["goals"] = stats.goals
            entry["assists"] = stats.assists
            entry["appearances"] = stats.appearances
            entry["avg_rating"] = float(stats.avg_rating) if stats.avg_rating else None

        shortlist_items.append(entry)

    return {
        "shortlist_name": shortlist.name,
        "items": shortlist_items,
    }


async def build_market_context(
    db: AsyncSession,
    club_id: uuid.UUID,
    position: str | None = None,
    max_budget: int | None = None,
    min_age: int | None = None,
    max_age: int | None = None,
    limit: int = 40,
) -> list[dict]:
    """Assemble all players outside the requesting club for LLM scouting context.

    Sale listing data (asking_price, sale_type) is included as optional enrichment
    when a player has an active open listing, but the absence of a sale does not
    exclude a player from recommendations.
    """
    from app.players.models import Player, PlayerPosition
    from app.sales.models import Sale, SaleStatus
    from app.stats.models import PlayerForm, PlayerStats

    stmt = select(Player).where(Player.current_club_id != club_id)

    if position:
        try:
            pos_enum = PlayerPosition(position.upper())
            stmt = stmt.where(Player.position == pos_enum)
        except ValueError:
            pass

    if min_age is not None:
        stmt = stmt.where(Player.age >= min_age)
    if max_age is not None:
        stmt = stmt.where(Player.age <= max_age)

    stmt = stmt.limit(limit)
    players_result = await db.execute(stmt)
    players = players_result.scalars().all()

    if not players:
        return []

    player_ids = [p.id for p in players]

    # Enrich with open sale data where available
    sales_result = await db.execute(
        select(Sale).where(
            Sale.player_id.in_(player_ids),
            Sale.status == SaleStatus.OPEN,
        )
    )
    sale_by_player: dict[uuid.UUID, Sale] = {
        s.player_id: s for s in sales_result.scalars().all()
    }

    forms_result = await db.execute(
        select(PlayerForm).where(PlayerForm.player_id.in_(player_ids))
    )
    form_by_player: dict[uuid.UUID, PlayerForm] = {
        f.player_id: f for f in forms_result.scalars().all()
    }

    stats_result = await db.execute(
        select(PlayerStats)
        .where(PlayerStats.player_id.in_(player_ids))
        .order_by(PlayerStats.updated_at.desc())
    )
    stats_by_player: dict[uuid.UUID, PlayerStats] = {}
    for s in stats_result.scalars().all():
        if s.player_id not in stats_by_player:
            stats_by_player[s.player_id] = s

    market = []
    for p in players:
        sale = sale_by_player.get(p.id)
        form = form_by_player.get(p.id)
        stats = stats_by_player.get(p.id)

        # Skip players that exceed the budget filter (only applies when listed)
        if max_budget is not None and sale and sale.asking_price and float(sale.asking_price) > max_budget:
            continue

        entry: dict = {
            "player_id": str(p.id),
            "name": p.name,
            "age": p.age,
            "position": p.position.value if p.position else None,
            "nationality": p.nationality,
            "open_to_offers": p.open_to_offers,
            "form_score": float(form.form_score) if form else None,
        }

        if sale:
            entry["sale_id"] = str(sale.id)
            entry["asking_price"] = float(sale.asking_price) if sale.asking_price else None
            entry["sale_type"] = sale.sale_type.value

        if stats:
            entry["goals"] = stats.goals
            entry["assists"] = stats.assists
            entry["appearances"] = stats.appearances
            entry["avg_rating"] = float(stats.avg_rating) if stats.avg_rating else None

        market.append(entry)

    return market
