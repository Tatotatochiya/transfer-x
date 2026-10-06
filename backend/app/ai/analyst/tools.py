"""The analyst's tools (AI analyst spec §4, Phase A).

Read-only, and scoped to the asking club: the club comes from the session,
never from the question, and each tool applies the same visibility rules as
the app's own pages (§6):

- other clubs' wages and budgets are never returned;
- an anonymous buyer or asker stays "an undisclosed club";
- interest in a player is shown only to his own club, and shortlists and
  views only as counts, never which clubs.

Each tool returns a `ToolResult`: rows of plain values (with a `path` to open
and, for players, `player_id` and `photo_url`), the total before the limit,
the filters it applied and when. TransferX does every count, filter and sort;
the model only chooses tools and words the answer.
"""
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Awaitable, Callable

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

MAX_ROWS = 50


@dataclass
class Ctx:
    db: AsyncSession
    club: object
    user: object


@dataclass
class ToolResult:
    kind: str  # "players", "listings", "squad", "money", "transfers", "history", "interest", "player"
    rows: list[dict]
    total: int
    filters: dict
    columns: list[str]
    note: str | None = None
    as_of: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="minutes"))

    def for_model(self) -> dict:
        return {"kind": self.kind, "total": self.total, "showing": len(self.rows), "filters": self.filters,
                "as_of": self.as_of, "note": self.note, "rows": self.rows}


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict
    run: Callable[..., Awaitable[ToolResult]]

    def schema(self) -> dict:
        return {"type": "function", "function": {
            "name": self.name, "description": self.description, "parameters": self.parameters}}


def _v(x):
    if isinstance(x, Decimal):
        return float(x)
    if isinstance(x, (date, datetime)):
        return x.isoformat()
    return getattr(x, "value", x)


def _limit(n) -> int:
    try:
        return max(1, min(int(n), MAX_ROWS))
    except (TypeError, ValueError):
        return 10


def _clean(filters: dict) -> dict:
    return {k: _v(v) for k, v in filters.items() if v not in (None, "", [])}


POSITIONS = ["GK", "DEF", "MID", "FWD"]


# ── Market ────────────────────────────────────────────────────────────────────


async def search_players(ctx: Ctx, position: str | None = None, min_age: int | None = None, max_age: int | None = None,
                         nationality: str | None = None, club: str | None = None, listed: bool | None = None,
                         max_value: float | None = None, min_value: float | None = None,
                         contract_ends_within_months: int | None = None, name: str | None = None,
                         sort_by: str = "value", sort_dir: str = "desc", limit: int = 10) -> ToolResult:
    """Players on the market (other clubs' and free agents), as the market
    page shows them. `listed` means a listing is open (transfer listed)."""
    from app.players import service as players_service
    from app.players.models import Contract
    from app.sales.models import Sale, SaleStatus

    sort_by = sort_by if sort_by in ("name", "age", "value", "goals", "assists", "avg_rating", "form_score") else "value"
    players, total = await players_service.list_market_players(
        ctx.db, is_authenticated=True, position=position if position in POSITIONS else None, status=None,
        open_to_offers=listed, search=name, min_age=min_age, max_age=max_age, nationality=nationality,
        club_search=club, min_market_value=Decimal(str(min_value)) if min_value else None,
        max_market_value=Decimal(str(max_value)) if max_value else None,
        contract_expiry_within_months=contract_ends_within_months, sort_by=sort_by,
        sort_dir="asc" if sort_dir == "asc" else "desc", page=1, page_size=min(_limit(limit) + 25, 100),
    )
    # The market, not the club's own squad ("5 listed midfielders" means
    # someone else's). Its own players are what the squad tool is for.
    def is_own(p) -> bool:
        if p.current_club_id is not None:
            return str(p.current_club_id) == str(ctx.club.id)
        # Added by the club itself and not yet under contract (squad_check's rule).
        return p.created_by_user_id is not None and str(p.created_by_user_id) == str(ctx.club.user_id)

    own = [p for p in players if is_own(p)]
    players = [p for p in players if p not in own][:_limit(limit)]
    total = max(0, total - len(own))
    ids = [p.id for p in players]
    sales = {}
    ends = {}
    if ids:
        for s in (await ctx.db.execute(select(Sale).where(Sale.player_id.in_(ids), Sale.status == SaleStatus.OPEN))).scalars():
            sales[s.player_id] = s
        for pid, end in (await ctx.db.execute(select(Contract.player_id, Contract.end_date).where(
                Contract.player_id.in_(ids), Contract.is_active.is_(True)))).all():
            ends[pid] = end
    rows = []
    for p in players:
        sale = sales.get(p.id)
        end = ends.get(p.id) or p.contract_expiry
        rows.append({
            "player": p.name, "player_id": str(p.id), "photo_url": p.photo_url,
            "position": _v(p.position), "age": p.age, "nationality": p.nationality,
            "club": p.current_club.name if p.current_club else (p.team_name or None),
            "contract_ends": _v(end) if end else None,
            "market_value": _v(p.market_value), "market_value_currency": p.market_value_currency,
            "listed": sale is not None,
            "asking_price": _v(sale.asking_price) if sale is not None else None,
            "path": f"/sales/{sale.id}" if sale is not None else f"/players/market/{p.id}",
        })
    return ToolResult("players", rows, total, _clean(dict(
        position=position, min_age=min_age, max_age=max_age, nationality=nationality, club=club, listed=listed,
        min_value=min_value, max_value=max_value, contract_ends_within_months=contract_ends_within_months,
        name=name, sort_by=sort_by, sort_dir=sort_dir)),
        ["player", "position", "age", "club", "contract_ends", "market_value", "listed", "asking_price"],
        note="market_value is the public estimate, in market_value_currency")


async def get_player(ctx: Ctx, name: str) -> ToolResult:
    """One player by name: his club, contract, listing and fee model, as any
    club may see them. Several matches come back as candidates."""
    from app.ai.assist import _player_facts, mentioned_players
    from app.players.models import Player

    found = await mentioned_players(ctx.db, name, ctx.club)
    if not found:
        # Not a surname match: a looser search, e.g. part of a name.
        rows = (await ctx.db.execute(select(Player).where(Player.name.ilike(f"%{name.strip()}%")).limit(5))).scalars().all()
        found = [{"player": p.name, "player_id": str(p.id), "path": f"/players/market/{p.id}"} for p in rows]
    out = []
    for m in found[:5]:
        player = await ctx.db.get(Player, uuid.UUID(m["player_id"]))
        if player is None:
            continue
        facts = await _player_facts(ctx.db, player.id, ctx.club.id)
        out.append({
            **{k: m.get(k) for k in ("club", "is_your_player", "listed_for_sale", "status") if k in m},
            "player": player.name, "player_id": str(player.id), "photo_url": player.photo_url,
            "position": facts["position"], "age": facts["age"], "nationality": facts["nationality"],
            "contract_ends": facts["contract_ends"],
            "fair_value": (facts.get("fee_model") or {}).get("fair_value"),
            "wage_weekly": facts["current_wage_weekly"], "wage_is_estimate": facts["current_wage_is_estimate"],
            "path": m["path"],
        })
    return ToolResult("player", out, len(out), {"name": name},
                      ["player", "club", "position", "age", "contract_ends", "fair_value", "listed_for_sale"],
                      note=None if out else f"No player called {name!r} on TransferX")


async def search_listings(ctx: Ctx, position: str | None = None, sale_type: str | None = None,
                          loan: bool | None = None, max_price: float | None = None,
                          ending_within_days: int | None = None, include_own: bool = False, limit: int = 10) -> ToolResult:
    """Open listings across the market: who is for sale or loan, at what
    asking price, until when."""
    from app.sales.models import Sale, SaleStatus, SaleType

    from sqlalchemy.orm import selectinload

    q = select(Sale).where(Sale.status == SaleStatus.OPEN).options(selectinload(Sale.player), selectinload(Sale.seller_club))
    if not include_own:
        q = q.where(Sale.seller_club_id != ctx.club.id)
    if sale_type in ("AUCTION", "OPEN_TO_OFFERS", "FIXED_PRICE"):
        q = q.where(Sale.sale_type == SaleType(sale_type))
    sales = list((await ctx.db.execute(q)).scalars())
    now = datetime.now(timezone.utc)

    def keep(s) -> bool:
        if s.player is None:
            return False
        if position in POSITIONS and _v(s.player.position) != position:
            return False
        avail = _v(s.availability)
        if loan is True and avail not in ("LOAN", "EITHER"):
            return False
        if loan is False and avail == "LOAN":
            return False
        if max_price and s.asking_price is not None and float(s.asking_price) > max_price:
            return False
        if ending_within_days and (s.deadline is None or (s.deadline if s.deadline.tzinfo else s.deadline.replace(tzinfo=timezone.utc)) > now + timedelta(days=ending_within_days)):
            return False
        return True

    sales = [s for s in sales if keep(s)]
    sales.sort(key=lambda s: (s.deadline is None, s.deadline or now))
    rows = [{
        "player": s.player.name, "player_id": str(s.player_id), "photo_url": s.player.photo_url,
        "position": _v(s.player.position), "age": s.player.age,
        "club": s.seller_club.name if s.seller_club else None, "type": _v(s.sale_type),
        "availability": _v(s.availability), "asking_price": _v(s.asking_price),
        "deadline": _v(s.deadline) if s.deadline else None, "path": f"/sales/{s.id}",
    } for s in sales[:_limit(limit)]]
    return ToolResult("listings", rows, len(sales), _clean(dict(
        position=position, sale_type=sale_type, loan=loan, max_price=max_price,
        ending_within_days=ending_within_days, include_own=include_own or None)),
        ["player", "position", "age", "club", "type", "asking_price", "deadline"])


# ── Our club ──────────────────────────────────────────────────────────────────


async def squad(ctx: Ctx, position: str | None = None, max_age: int | None = None, min_age: int | None = None,
                contract_ends_within_months: int | None = None, sort_by: str = "wage", limit: int = 30) -> ToolResult:
    """The club's own players with their contracts: wage, end date, the
    club's own valuation. Only the club itself sees its wages."""
    from app.clubs import squad_check

    players = await squad_check.squad(ctx.db, ctx.club.id)
    today = date.today()
    rows = []
    for p in players:
        c = next((x for x in p.contracts if x.is_active and str(x.club_id) == str(ctx.club.id)), None)
        end = (c.end_date if c else None) or p.contract_expiry
        if position in POSITIONS and _v(p.position) != position:
            continue
        if max_age and (p.age or 0) > max_age or min_age and (p.age or 0) < min_age:
            continue
        if contract_ends_within_months and (end is None or end > today + timedelta(days=30 * contract_ends_within_months)):
            continue
        rows.append({
            "player": p.name, "player_id": str(p.id), "photo_url": p.photo_url, "position": _v(p.position),
            "age": p.age, "contract_ends": _v(end) if end else None,
            "wage_weekly": _v(c.wage_weekly) if c else None, "your_valuation": _v(c.club_valuation) if c else None,
            "listed": bool(p.open_to_offers), "path": f"/players/market/{p.id}",
        })
    key = {"wage": lambda r: -(r["wage_weekly"] or 0), "age": lambda r: r["age"] or 0,
           "contract_end": lambda r: r["contract_ends"] or "9999", "valuation": lambda r: -(r["your_valuation"] or 0),
           "name": lambda r: r["player"]}.get(sort_by, lambda r: -(r["wage_weekly"] or 0))
    rows.sort(key=key)
    return ToolResult("squad", rows[:_limit(limit)], len(rows), _clean(dict(
        position=position, min_age=min_age, max_age=max_age,
        contract_ends_within_months=contract_ends_within_months, sort_by=sort_by)),
        ["player", "position", "age", "contract_ends", "wage_weekly", "your_valuation", "listed"])


async def money(ctx: Ctx) -> ToolResult:
    """The club's own budget: transfer budget, held for open offers,
    committed, remaining, and wage room. Never another club's."""
    from app.ai.assist import _budget_facts

    b = await _budget_facts(ctx.db, ctx.club.id) or {}
    rows = [{"metric": k, "value": _v(v)} for k, v in b.items()]
    return ToolResult("money", rows, len(rows), {}, ["metric", "value"],
                      note="transfer_budget_remaining is free now; reserved is held for open offers; committed is agreed deals")


# ── Our transfers ─────────────────────────────────────────────────────────────

_COLUMNS = {"talking": "Talking", "offers": "Offers", "fee_agreed": "Fee agreed", "terms": "Personal terms",
            "paperwork": "Paperwork", "done": "Done"}


async def transfers(ctx: Ctx, side: str = "BOTH", stage: str | None = None, your_move: bool | None = None,
                    deadline_within_days: int | None = None, limit: int = 30) -> ToolResult:
    """Every player the club is buying or selling now, once (the Transfers
    board): stage, whose move, deadline, the other club (masked if anonymous)."""
    from app.board.service import get_board

    board = await get_board(ctx.db, ctx.club.id, side if side in ("BUYING", "SELLING") else "BOTH")
    now = datetime.now(timezone.utc)
    rows = []
    for col in board.columns:
        if stage and stage != col.key:
            continue
        for c in col.cards:
            if your_move is not None and (c.whose_move.value == "your") != your_move:
                continue
            if deadline_within_days and (c.deadline is None or (c.deadline if c.deadline.tzinfo else c.deadline.replace(tzinfo=timezone.utc)) > now + timedelta(days=deadline_within_days)):
                continue
            rows.append({
                "player": c.player_name, "player_id": str(c.player_id), "photo_url": c.player_photo_url,
                "side": c.side.lower(), "stage": _COLUMNS.get(c.column, c.column), "other_club": c.counterparty,
                "amount": _v(c.amount), "status": c.detail, "your_move": c.whose_move.value == "your",
                "deadline": _v(c.deadline) if c.deadline else None, "path": c.link,
            })
    return ToolResult("transfers", rows[:_limit(limit)], len(rows), _clean(dict(
        side=side if side != "BOTH" else None, stage=stage, your_move=your_move, deadline_within_days=deadline_within_days)),
        ["player", "side", "stage", "other_club", "amount", "status", "deadline"])


async def history(ctx: Ctx, side: str = "BOTH", outcome: str | None = None, days: int | None = None,
                  search: str | None = None, limit: int = 30) -> ToolResult:
    """Transfers that finished or ended without one: completed, collapsed,
    offers rejected, withdrawn or expired, closed enquiries, ended listings."""
    from app.board.service import get_history

    data = await get_history(ctx.db, ctx.club.id, side=side if side in ("BUYING", "SELLING") else "BOTH",
                             q=search, outcome=outcome if outcome in ("completed", "ended") else None,
                             page=1, page_size=1000)
    items = data["items"]
    if days:
        since = datetime.now(timezone.utc) - timedelta(days=days)
        items = [c for c in items if c.updated_at and (c.updated_at if c.updated_at.tzinfo else c.updated_at.replace(tzinfo=timezone.utc)) >= since]
    rows = [{
        "player": c.player_name, "player_id": str(c.player_id), "photo_url": c.player_photo_url,
        "side": c.side.lower(), "outcome": c.detail, "other_club": c.counterparty, "amount": _v(c.amount),
        "when": _v(c.updated_at) if c.updated_at else None, "path": c.link,
    } for c in items]
    return ToolResult("history", rows[:_limit(limit)], len(rows), _clean(dict(
        side=side if side != "BOTH" else None, outcome=outcome, days=days, search=search)),
        ["player", "side", "outcome", "other_club", "amount", "when"])


# ── Interest in our players ───────────────────────────────────────────────────


async def interest_in_my_players(ctx: Ctx, days: int = 7, player: str | None = None, limit: int = 20) -> ToolResult:
    """Interest in the club's own players over the last `days`: enquiries,
    offers and bids received, how many other clubs shortlisted him, and how
    many viewed him. Counts only: never which clubs shortlisted or viewed."""
    from app.clubs import squad_check
    from app.enquiries.models import Enquiry
    from app.offers.models import Offer, OfferStatus
    from app.players.models import PlayerView
    from app.sales.models import Bid, Sale
    from app.scouting.models import Shortlist, ShortlistItem

    days = max(1, min(int(days or 7), 365))
    since = datetime.now(timezone.utc) - timedelta(days=days)
    players = await squad_check.squad(ctx.db, ctx.club.id)
    if player:
        players = [p for p in players if player.lower() in p.name.lower()]
    ids = [p.id for p in players]
    counts: dict = {pid: {"enquiries": 0, "offers": 0, "bids": 0, "shortlisted_by_clubs": 0, "viewed_by_clubs": 0} for pid in ids}
    if ids:
        for pid, n in (await ctx.db.execute(select(Enquiry.player_id, func.count()).where(
                Enquiry.player_id.in_(ids), Enquiry.to_club_id == ctx.club.id, Enquiry.created_at >= since)
                .group_by(Enquiry.player_id))).all():
            counts[pid]["enquiries"] = n
        for pid, n in (await ctx.db.execute(select(Offer.player_id, func.count()).where(
                Offer.player_id.in_(ids), Offer.to_club_id == ctx.club.id, Offer.status != OfferStatus.DRAFT,
                Offer.created_at >= since).group_by(Offer.player_id))).all():
            counts[pid]["offers"] = n
        for pid, n in (await ctx.db.execute(select(Sale.player_id, func.count()).join(Bid, Bid.sale_id == Sale.id).where(
                Sale.player_id.in_(ids), Sale.seller_club_id == ctx.club.id, Bid.created_at >= since)
                .group_by(Sale.player_id))).all():
            counts[pid]["bids"] = n
        for pid, n in (await ctx.db.execute(select(ShortlistItem.player_id, func.count(func.distinct(Shortlist.club_id)))
                .join(Shortlist, Shortlist.id == ShortlistItem.shortlist_id).where(
                ShortlistItem.player_id.in_(ids), Shortlist.club_id != ctx.club.id, ShortlistItem.created_at >= since)
                .group_by(ShortlistItem.player_id))).all():
            counts[pid]["shortlisted_by_clubs"] = n
        for pid, n in (await ctx.db.execute(select(PlayerView.player_id, func.count(func.distinct(PlayerView.club_id))).where(
                PlayerView.player_id.in_(ids), PlayerView.club_id != ctx.club.id, PlayerView.day >= since.date())
                .group_by(PlayerView.player_id))).all():
            counts[pid]["viewed_by_clubs"] = n
    rows = []
    for p in players:
        c = counts[p.id]
        total = sum(c.values())
        if total == 0:
            continue
        rows.append({"player": p.name, "player_id": str(p.id), "photo_url": p.photo_url, "position": _v(p.position),
                     **c, "path": f"/players/market/{p.id}"})
    rows.sort(key=lambda r: -(r["enquiries"] * 3 + r["offers"] * 4 + r["bids"] * 4 + r["shortlisted_by_clubs"] * 2 + r["viewed_by_clubs"]))
    return ToolResult("interest", rows[:_limit(limit)], len(rows), _clean(dict(days=days, player=player)),
                      ["player", "position", "enquiries", "offers", "bids", "shortlisted_by_clubs", "viewed_by_clubs"],
                      note="Shortlists and views are counts of other clubs; TransferX never says which clubs")


# ── The catalogue ─────────────────────────────────────────────────────────────

_INT = {"type": "integer"}
_NUM = {"type": "number"}
_STR = {"type": "string"}
_BOOL = {"type": "boolean"}
_POS = {"type": "string", "enum": POSITIONS, "description": "GK, DEF, MID or FWD"}
_SIDE = {"type": "string", "enum": ["BOTH", "BUYING", "SELLING"]}
_LIM = {"type": "integer", "description": f"rows to return, at most {MAX_ROWS}"}

TOOLS: dict[str, Tool] = {t.name: t for t in [
    Tool("search_players", "Search players at other clubs and free agents (the player market). Use for 'show me "
         "midfielders who are transfer listed', 'left-backs under 24 under £10m', 'strikers whose contract ends next "
         "year'. listed=true means a listing is open (transfer listed).",
         {"type": "object", "properties": {
             "position": _POS, "min_age": _INT, "max_age": _INT, "nationality": _STR,
             "club": {"type": "string", "description": "the player's club name, or part of it"},
             "listed": _BOOL, "min_value": {"type": "number", "description": "pounds"},
             "max_value": {"type": "number", "description": "pounds"},
             "contract_ends_within_months": _INT, "name": _STR,
             "sort_by": {"type": "string", "enum": ["value", "age", "name", "goals", "assists", "avg_rating", "form_score"]},
             "sort_dir": {"type": "string", "enum": ["asc", "desc"]}, "limit": _LIM}}, search_players),
    Tool("get_player", "Look up one player by name: his club on TransferX, contract, listing and fair value. Always "
         "use this before saying anything about a named player.",
         {"type": "object", "properties": {"name": _STR}, "required": ["name"]}, get_player),
    Tool("search_listings", "Open listings across the market (players other clubs are selling or loaning), with "
         "asking price and deadline. Use for 'who's for sale', 'auctions ending this week', 'loan options'.",
         {"type": "object", "properties": {
             "position": _POS, "sale_type": {"type": "string", "enum": ["OPEN_TO_OFFERS", "AUCTION", "FIXED_PRICE"]},
             "loan": _BOOL, "max_price": {"type": "number", "description": "pounds"}, "ending_within_days": _INT,
             "include_own": _BOOL, "limit": _LIM}}, search_listings),
    Tool("squad", "The asking club's own players with contracts: wage, end date, the club's valuation, listed. Use "
         "for 'our highest earners', 'who is out of contract next summer', 'our defenders'.",
         {"type": "object", "properties": {
             "position": _POS, "min_age": _INT, "max_age": _INT, "contract_ends_within_months": _INT,
             "sort_by": {"type": "string", "enum": ["wage", "age", "contract_end", "valuation", "name"]},
             "limit": _LIM}}, squad),
    Tool("money", "The asking club's budget now: transfer budget, held for open offers, committed, remaining, wage room.",
         {"type": "object", "properties": {}}, money),
    Tool("transfers", "Every player the club is buying or selling now (the Transfers board): stage, other club, "
         "amount, whose move, deadline. Use for 'what's waiting on us', 'offers expiring this week', 'where is the "
         "Bogle deal'.",
         {"type": "object", "properties": {
             "side": _SIDE, "stage": {"type": "string", "enum": list(_COLUMNS)}, "your_move": _BOOL,
             "deadline_within_days": _INT, "limit": _LIM}}, transfers),
    Tool("history", "Transfers that finished or ended without one: completed deals, collapsed deals, offers rejected, "
         "withdrawn or expired, closed enquiries, ended listings.",
         {"type": "object", "properties": {
             "side": _SIDE, "outcome": {"type": "string", "enum": ["completed", "ended"]}, "days": _INT,
             "search": {"type": "string", "description": "a player or club name"}, "limit": _LIM}}, history),
    Tool("interest_in_my_players", "Interest in the asking club's own players over the last N days: enquiries, offers "
         "and bids received, and how many other clubs shortlisted or viewed each. Use for 'which of our players had "
         "interest this week'. Counts only, never which clubs; there is no tool for interest in other clubs' players.",
         {"type": "object", "properties": {"days": _INT, "player": _STR, "limit": _LIM}}, interest_in_my_players),
]}


async def run_tool(ctx: Ctx, name: str, args: dict) -> ToolResult:
    tool = TOOLS.get(name)
    if tool is None:
        raise ValueError(f"Unknown tool {name}")
    allowed = set(tool.parameters.get("properties", {}))
    clean = {k: v for k, v in (args or {}).items() if k in allowed and v is not None}
    return await tool.run(ctx, **clean)


def _register_phase_b() -> None:
    """Phase B's tools (tools_b.py) join the same catalogue."""
    from app.ai.analyst.tools_b import PHASE_B

    for name, description, parameters, run in PHASE_B:
        TOOLS[name] = Tool(name, description, parameters, run)


_register_phase_b()
