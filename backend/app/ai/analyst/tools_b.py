"""The analyst's Phase B tools (AI analyst spec §4.1, §4.2, §4.3, §4.5).

Same rules as Phase A (tools.py): read-only, the club from the session, the
app's own visibility rules. Statistics, injuries and completed transfers are
public; loans, approvals, the team's activity and a transfer's conversation
are the asking club's own.
"""
import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, or_, select

from app.ai.analyst.tools import POSITIONS, Ctx, ToolResult, _clean, _limit, _v


async def _resolve(ctx: Ctx, names: list[str] | None) -> tuple[list, list[str]]:
    """Players by name (surname or full), and the names nobody matched."""
    from app.ai.assist import mentioned_players
    from app.players.models import Player

    found, missing = [], []
    for name in (names or [])[:6]:
        hits = await mentioned_players(ctx.db, str(name), ctx.club)
        if not hits:
            rows = (await ctx.db.execute(select(Player).where(Player.name.ilike(f"%{str(name).strip()}%")).limit(1))).scalars().all()
            hits = [{"player_id": str(p.id)} for p in rows]
        if not hits:
            missing.append(str(name))
            continue
        p = await ctx.db.get(Player, uuid.UUID(hits[0]["player_id"]))
        if p is not None and p not in found:
            found.append(p)
    return found, missing


async def _squad_players(ctx: Ctx, position: str | None):
    from app.clubs import squad_check

    players = await squad_check.squad(ctx.db, ctx.club.id)
    return [p for p in players if not position or _v(p.position) == position]


def _per90(n, minutes) -> float | None:
    if not minutes or n is None:
        return None
    return round(n * 90 / minutes, 2)


async def _season_lines(ctx: Ctx, players, season: str | None) -> dict:
    """One line per player for a season (default: his latest), summed across
    competitions; ratings weighted by minutes."""
    from app.stats.models import PlayerStats

    ids = [p.id for p in players]
    if not ids:
        return {}
    rows = (await ctx.db.execute(select(PlayerStats).where(PlayerStats.player_id.in_(ids)))).scalars().all()
    by_player: dict = {}
    for r in rows:
        by_player.setdefault(r.player_id, []).append(r)
    out = {}
    for pid, lines in by_player.items():
        chosen = season or max(str(x.season) for x in lines)
        lines = [x for x in lines if str(x.season) == str(chosen)]
        if not lines:
            continue
        mins = sum(x.minutes or 0 for x in lines)
        tot = lambda f: sum((getattr(x, f) or 0) for x in lines)  # noqa: E731
        rated = [(x.avg_rating, x.minutes or 0) for x in lines if x.avg_rating]
        rating = (sum(float(r) * m for r, m in rated) / sum(m for _, m in rated)) if rated and sum(m for _, m in rated) else None
        passes = [(x.pass_accuracy, x.passes_total or 0) for x in lines if x.pass_accuracy is not None]
        out[pid] = {
            "season": str(chosen),
            "team": lines[0].team_name, "competitions": ", ".join(sorted({x.league_name for x in lines if x.league_name})),
            "appearances": tot("appearances"), "minutes": mins, "goals": tot("goals"), "assists": tot("assists"),
            "goals_per90": _per90(tot("goals"), mins), "assists_per90": _per90(tot("assists"), mins),
            "key_passes_per90": _per90(tot("key_passes"), mins), "tackles_per90": _per90(tot("tackles_total"), mins),
            "interceptions_per90": _per90(tot("interceptions"), mins),
            "dribbles_per90": _per90(tot("dribbles_success"), mins),
            "pass_accuracy": round(sum(float(a) * n for a, n in passes) / sum(n for _, n in passes), 1)
            if passes and sum(n for _, n in passes) else None,
            "avg_rating": round(rating, 2) if rating else None,
            "saves": tot("saves"), "goals_conceded": tot("goals_conceded"),
        }
    return out


STAT_COLUMNS = ["player", "season", "team", "appearances", "minutes", "goals", "assists", "goals_per90",
                "assists_per90", "avg_rating"]
SORTABLE = {"minutes", "goals", "assists", "goals_per90", "assists_per90", "key_passes_per90", "tackles_per90",
            "interceptions_per90", "dribbles_per90", "pass_accuracy", "avg_rating", "appearances", "saves"}


async def player_stats(ctx: Ctx, names: list[str] | None = None, our_squad: bool = False, position: str | None = None,
                       season: str | None = None, sort_by: str = "minutes", limit: int = 20) -> ToolResult:
    """A season's statistics, summed across competitions: appearances,
    minutes, goals, assists, per-90 figures, rating. For named players, or
    for the club's own squad (optionally one position)."""
    if names:
        players, missing = await _resolve(ctx, names)
    else:
        players, missing = (await _squad_players(ctx, position if position in POSITIONS else None) if our_squad else []), []
    lines = await _season_lines(ctx, players, season)
    rows = []
    for p in players:
        s = lines.get(p.id)
        rows.append({"player": p.name, "player_id": str(p.id), "photo_url": p.photo_url, "position": _v(p.position),
                     **(s or {"season": None}), "path": f"/players/market/{p.id}"})
    key = sort_by if sort_by in SORTABLE else "minutes"
    if not names:
        rows.sort(key=lambda r: -(r.get(key) or 0))
    note = ("No statistics for: " + ", ".join(missing)) if missing else None
    if any(r.get("season") is None for r in rows):
        note = (note + ". " if note else "") + "Some players have no statistics on TransferX (their league isn't covered)."
    return ToolResult("stats", rows[:_limit(limit)], len(rows), _clean(dict(
        names=", ".join(names) if names else None, our_squad=our_squad or None, position=position, season=season,
        sort_by=None if names else key)), STAT_COLUMNS, note=note)


async def compare_players(ctx: Ctx, names: list[str], season: str | None = None) -> ToolResult:
    """Two to four players side by side: club, age, contract end, fair value,
    and the season's statistics per 90."""
    from app.ai.assist import _player_facts
    from app.players.service import get_owning_club_id
    from app.clubs.models import Club

    players, missing = await _resolve(ctx, (names or [])[:4])
    lines = await _season_lines(ctx, players, season)
    rows = []
    for p in players:
        facts = await _player_facts(ctx.db, p.id, ctx.club.id)
        owner = await get_owning_club_id(ctx.db, p)
        club = (await ctx.db.execute(select(Club.name).where(Club.id == owner))).scalar_one_or_none() if owner else p.team_name
        rows.append({
            "player": p.name, "player_id": str(p.id), "photo_url": p.photo_url, "position": facts["position"],
            "age": facts["age"], "club": club, "contract_ends": facts["contract_ends"],
            "fair_value": (facts.get("fee_model") or {}).get("fair_value"),
            **{k: v for k, v in (lines.get(p.id) or {}).items() if k != "team"},
            "path": f"/players/market/{p.id}",
        })
    return ToolResult("comparison", rows, len(rows), _clean(dict(names=", ".join(names or []), season=season)),
                      ["player", "club", "age", "contract_ends", "fair_value", "minutes", "goals_per90",
                       "assists_per90", "key_passes_per90", "avg_rating"],
                      note=("Couldn't find: " + ", ".join(missing)) if missing else None)


async def injuries(ctx: Ctx, names: list[str] | None = None, our_squad: bool = False, current_only: bool = False,
                   months: int = 12, limit: int = 30) -> ToolResult:
    """Injuries from the match data: the latest per player with when, what and
    games missed, and how many games he's missed in the last N months."""
    from app.players.models import PlayerInjury

    players = (await _resolve(ctx, names))[0] if names else (await _squad_players(ctx, None) if our_squad else [])
    ids = [p.id for p in players]
    since = date.today() - timedelta(days=30 * max(1, min(int(months or 12), 36)))
    rows = []
    if ids:
        recs = (await ctx.db.execute(select(PlayerInjury).where(PlayerInjury.player_id.in_(ids))
                                     .order_by(PlayerInjury.fixture_date.desc()))).scalars().all()
        by: dict = {}
        for r in recs:
            by.setdefault(r.player_id, []).append(r)
        today = date.today()
        for p in players:
            recs = by.get(p.id, [])
            recent = [r for r in recs if r.fixture_date and r.fixture_date >= since]
            last = recs[0] if recs else None
            out_now = bool(last and ((last.end_date and last.end_date >= today) or
                                     (not last.end_date and last.fixture_date and last.fixture_date >= today - timedelta(days=14))))
            if current_only and not out_now:
                continue
            if not recs and not names:
                continue
            rows.append({
                "player": p.name, "player_id": str(p.id), "photo_url": p.photo_url, "position": _v(p.position),
                "injured_now": out_now, "latest_injury": (last.injury_type or last.reason) if last else None,
                "latest_date": _v(last.fixture_date) if last and last.fixture_date else None,
                "expected_back": _v(last.end_date) if last and last.end_date else None,
                "games_missed_period": len(recent), "path": f"/players/market/{p.id}",
            })
    rows.sort(key=lambda r: (not r["injured_now"], -(r["games_missed_period"] or 0)))
    return ToolResult("injuries", rows[:_limit(limit)], len(rows), _clean(dict(
        names=", ".join(names) if names else None, our_squad=our_squad or None, current_only=current_only or None,
        months=months)),
        ["player", "position", "injured_now", "latest_injury", "latest_date", "expected_back", "games_missed_period"],
        note="From match-day injury reports; games missed counts the fixtures he was listed out for")


async def recent_transfers(ctx: Ctx, position: str | None = None, club: str | None = None, days: int = 180,
                           min_fee: float | None = None, limit: int = 20) -> ToolResult:
    """Completed transfers: on TransferX (with the agreed fee) and the wider
    market's history (fee as reported). Public, as on Recent Transfers."""
    from app.deals.models import Deal, DealStatus
    from app.players.models import Player, PlayerTransfer
    from sqlalchemy.orm import selectinload

    days = max(7, min(int(days or 180), 1095))
    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows = []
    deals = (await ctx.db.execute(select(Deal).where(Deal.status == DealStatus.COMPLETED, Deal.completed_at >= since)
                                  .options(selectinload(Deal.player), selectinload(Deal.buyer_club),
                                           selectinload(Deal.seller_club)))).scalars().all()
    for d in deals:
        if d.player is None:
            continue
        rows.append({"player": d.player.name, "player_id": str(d.player_id), "photo_url": d.player.photo_url,
                     "position": _v(d.player.position), "from": d.seller_club.name if d.seller_club else None,
                     "to": d.buyer_club.name if d.buyer_club else None, "fee": _v(d.agreed_fee),
                     "fee_reported": None, "date": _v(d.completed_at.date()), "source": "TransferX",
                     "path": f"/players/market/{d.player_id}"})
    # Loan returns aren't transfers anyone is asking about.
    ext_q = (select(PlayerTransfer, Player).join(Player, Player.id == PlayerTransfer.player_id)
             .where(PlayerTransfer.transfer_date >= since.date(),
                    func.coalesce(PlayerTransfer.fee_display, "").notin_(["Return from loan", "Back from Loan"])))
    if position in POSITIONS:
        from app.players.models import PlayerPosition

        ext_q = ext_q.where(Player.position == PlayerPosition(position))
    if club:
        like = f"%{club}%"
        ext_q = ext_q.where((PlayerTransfer.team_in_name.ilike(like)) | (PlayerTransfer.team_out_name.ilike(like)))
    ext_total = (await ctx.db.execute(select(func.count()).select_from(ext_q.subquery()))).scalar_one()
    ext = (await ctx.db.execute(ext_q.order_by(PlayerTransfer.transfer_date.desc()).limit(_limit(limit) + 20))).all()
    for t, p in ext:
        rows.append({"player": p.name, "player_id": str(p.id), "photo_url": p.photo_url, "position": _v(p.position),
                     "from": t.team_out_name, "to": t.team_in_name, "fee": None, "fee_reported": t.fee_display,
                     "date": _v(t.transfer_date), "source": "Reported", "path": f"/players/market/{p.id}"})
    if position in POSITIONS:
        rows = [r for r in rows if r["position"] == position]
    if club:
        c = club.lower()
        rows = [r for r in rows if c in (r["from"] or "").lower() or c in (r["to"] or "").lower()]
    if min_fee:
        rows = [r for r in rows if r["fee"] and r["fee"] >= min_fee]
    rows.sort(key=lambda r: r["date"] or "", reverse=True)
    total = len([r for r in rows if r["source"] == "TransferX"]) + (0 if min_fee else ext_total)
    return ToolResult("transfers_market", rows[:_limit(limit)], total, _clean(dict(
        position=position, club=club, days=days, min_fee=min_fee)),
        ["player", "position", "from", "to", "fee", "fee_reported", "date"],
        note="fee is the agreed fee on TransferX; fee_reported is as published elsewhere (loan, free, or a figure)")


async def comparable_transfers(ctx: Ctx, name: str) -> ToolResult:
    """Completed transfers of similar players (same position, age within 3)
    in the last 18 months: what players like him have gone for."""
    from app.ai.assist import _comparables, _player_facts

    players, missing = await _resolve(ctx, [name])
    if not players:
        return ToolResult("comparables", [], 0, {"name": name}, [], note=f"No player called {name!r} on TransferX")
    p = players[0]
    facts = await _player_facts(ctx.db, p.id, ctx.club.id)
    comps = await _comparables(ctx.db, facts, p.id)
    rows = [{**c, "fee_reported": None, "source": "TransferX", "path": None} for c in comps]
    # Few deals complete on TransferX yet, so add reported transfers of
    # similar players (same position, age now within 3) that carry a fee.
    # Reported fees are sparser, so they look back three years.
    from app.players.models import Player, PlayerPosition, PlayerTransfer

    if facts.get("position"):
        since = date.today() - timedelta(days=3 * 365)
        q = (select(PlayerTransfer, Player).join(Player, Player.id == PlayerTransfer.player_id)
             .where(Player.position == PlayerPosition(facts["position"]), Player.id != p.id,
                    PlayerTransfer.transfer_date >= since,
                    # A figure in the fee: "€ 15M", not "Free" or "Transfer".
                    or_(*[PlayerTransfer.fee_display.like(f"%{d}%") for d in "0123456789"])))
        if facts.get("age"):
            q = q.where(Player.age.between(facts["age"] - 3, facts["age"] + 3))
        for t, other in (await ctx.db.execute(q.order_by(PlayerTransfer.transfer_date.desc()).limit(60))).all():
            fee = (t.fee_display or "").strip()
            if not any(ch.isdigit() for ch in fee):
                continue  # "Free", "Loan" and the like say nothing about price
            rows.append({"player": other.name, "player_id": str(other.id), "photo_url": other.photo_url,
                         "age": other.age, "fee": None, "fee_reported": fee, "completed": _v(t.transfer_date),
                         "from": t.team_out_name, "to": t.team_in_name, "source": "Reported",
                         "path": f"/players/market/{other.id}"})
            if len(rows) >= 12:
                break
    return ToolResult("comparables", rows, len(rows), {"name": p.name, "position": facts["position"], "age": facts["age"]},
                      ["player", "age", "fee", "fee_reported", "from", "to", "completed"],
                      note=("fee is the agreed fee on TransferX; fee_reported is as published elsewhere, in its own currency"
                            if rows else "No comparable transfers: none on TransferX in 18 months, none reported with a fee in 3 years"))


async def loans(ctx: Ctx, direction: str = "both", active_only: bool = True, limit: int = 30) -> ToolResult:
    """The club's loans: players out on loan (and when they return) and
    players in on loan, with fee, wage share and any option or obligation."""
    from sqlalchemy import or_
    from sqlalchemy.orm import selectinload

    from app.loans.models import LoanStatus, PlayerLoan

    q = select(PlayerLoan).options(selectinload(PlayerLoan.player), selectinload(PlayerLoan.parent_club),
                                   selectinload(PlayerLoan.loanee_club))
    if direction == "out":
        q = q.where(PlayerLoan.parent_club_id == ctx.club.id)
    elif direction == "in":
        q = q.where(PlayerLoan.loanee_club_id == ctx.club.id)
    else:
        q = q.where(or_(PlayerLoan.parent_club_id == ctx.club.id, PlayerLoan.loanee_club_id == ctx.club.id))
    if active_only:
        q = q.where(PlayerLoan.status == LoanStatus.ACTIVE)
    loans_ = (await ctx.db.execute(q.order_by(PlayerLoan.end_date))).scalars().all()
    rows = []
    for ln in loans_:
        out = str(ln.parent_club_id) == str(ctx.club.id)
        rows.append({
            "player": ln.player.name if ln.player else None, "player_id": str(ln.player_id),
            "photo_url": ln.player.photo_url if ln.player else None,
            "direction": "out" if out else "in",
            "other_club": (ln.loanee_club.name if out else ln.parent_club.name) if (ln.loanee_club and ln.parent_club) else None,
            "start": _v(ln.start_date), "end": _v(ln.end_date), "loan_fee": _v(ln.loan_fee),
            "wage_share_pct": round(float(ln.wage_split_pct) * 100) if ln.wage_split_pct is not None else None,
            "option_to_buy": _v(ln.option_to_buy), "obligation": bool(ln.obligation_to_buy),
            "status": _v(ln.status), "path": f"/players/market/{ln.player_id}",
        })
    return ToolResult("loans", rows[:_limit(limit)], len(rows), _clean(dict(direction=direction, active_only=active_only)),
                      ["player", "direction", "other_club", "start", "end", "loan_fee", "wage_share_pct", "option_to_buy"])


async def approvals(ctx: Ctx, status: str = "PENDING", limit: int = 30) -> ToolResult:
    """The club's spending approvals. Deciders see the club's queue; others
    see only the requests they made, as on the Approvals page."""
    from fastapi import HTTPException

    from app.approvals import service as approvals_service
    from app.approvals.models import ApprovalStatus
    from app.clubs.capabilities import Capability, ensure_club_capability
    from app.notifications.copy import approval_player

    try:
        await ensure_club_capability(ctx.db, ctx.user, Capability.APPROVE_ACTIONS)
        mine_only = None
    except HTTPException:
        mine_only = ctx.user.id
    st = ApprovalStatus(status) if status in ApprovalStatus.__members__ else None
    items = await approvals_service.list_approvals(ctx.db, ctx.club.id, status=st, requested_by_user_id=mine_only)
    rows = []
    for a in items[:_limit(limit)]:
        pid, pname, photo = await approval_player(ctx.db, a)
        from app.auth.models import User

        who = await ctx.db.get(User, a.requested_by_user_id)
        rows.append({"what": a.summary, "player": pname, "player_id": str(pid) if pid else None, "photo_url": photo,
                     "amount": _v(a.amount), "asked_by": who.display_label if who else None, "status": _v(a.status),
                     "expires": _v(a.expires_at), "path": f"/club/approvals?id={a.id}"})
    return ToolResult("approvals", rows, len(items), _clean(dict(status=status, only_yours=bool(mine_only) or None)),
                      ["what", "amount", "asked_by", "status", "expires"])


async def team_activity(ctx: Ctx, days: int = 7, person: str | None = None, limit: int = 40) -> ToolResult:
    """What the club's own people did on TransferX (its audit trail): who,
    what, when. Never another club's activity."""
    from app.audit.models import AuditEvent
    from app.auth.models import User
    from app.notifications import service as notif_service

    days = max(1, min(int(days or 7), 90))
    since = datetime.now(timezone.utc) - timedelta(days=days)
    members = await notif_service.club_member_user_ids(ctx.db, ctx.club.id)
    if not members:
        return ToolResult("activity", [], 0, {"days": days}, [])
    users = {u.id: u for u in (await ctx.db.execute(select(User).where(User.id.in_(members)))).scalars()}
    if person:
        p = person.lower()
        members = [m for m in members if users.get(m) and (p in users[m].display_label.lower() or p in users[m].email.lower())]
    events = (await ctx.db.execute(select(AuditEvent).where(AuditEvent.actor_user_id.in_(members), AuditEvent.created_at >= since)
                                   .order_by(AuditEvent.created_at.desc()).limit(500))).scalars().all()
    events = [e for e in events if not (e.action or "").startswith("admin.") and e.description]
    rows = [{"when": _v(e.created_at), "who": users[e.actor_user_id].display_label if e.actor_user_id in users else None,
             "what": e.description, "path": None} for e in events]
    return ToolResult("activity", rows[:_limit(limit)], len(rows), _clean(dict(days=days, person=person)),
                      ["when", "who", "what"])


async def conversation(ctx: Ctx, player: str, limit: int = 20) -> ToolResult:
    """The latest messages about one of the club's transfers (by player name):
    the enquiry, offer, deal and agent messages it may read, newest last."""
    from app.board.service import get_board
    from app.conversation import service as conv_service

    board = await get_board(ctx.db, ctx.club.id)
    cards = [c for col in board.columns for c in col.cards] + list(board.closed)
    p = player.lower()
    match = next((c for c in cards if p in c.player_name.lower() and c.kind in ("offer", "deal", "enquiry")), None)
    if match is None:
        return ToolResult("conversation", [], 0, {"player": player}, [],
                          note=f"No transfer with {player} on your board, so no conversation")
    t = await conv_service.resolve(ctx.db, ctx.club.id, **{f"{match.kind}_id": match.entity_id})
    msgs = await conv_service.messages(ctx.db, t, ctx.user)
    rows = [{"when": _v(m["created_at"]), "who": m["author"], "audience": m["audience_label"],
             "where": m["context"], "text": m["body"][:400], "path": match.link} for m in msgs][-_limit(limit):]
    return ToolResult("conversation", rows, len(msgs), {"player": match.player_name},
                      ["when", "who", "audience", "text"])


_NAMES = {"type": "array", "items": {"type": "string"}, "description": "players' names, as the user wrote them"}
_INT = {"type": "integer"}
_POS = {"type": "string", "enum": POSITIONS}
_LIM = {"type": "integer"}

PHASE_B = [
    ("player_stats", "A season's statistics (appearances, minutes, goals, assists, per-90 figures, rating), summed "
     "across competitions. For named players, or for our_squad=true (optionally one position). Use for 'our "
     "midfielders by minutes this season', 'Isak's goals this season'. season like '2025'; default his latest.",
     {"type": "object", "properties": {"names": _NAMES, "our_squad": {"type": "boolean"}, "position": _POS,
                                       "season": {"type": "string"},
                                       "sort_by": {"type": "string", "enum": sorted(SORTABLE)}, "limit": _LIM}},
     player_stats),
    ("compare_players", "Compare 2-4 named players side by side: club, age, contract end, fair value, and per-90 "
     "statistics. Use for 'compare Isak and Watkins'.",
     {"type": "object", "properties": {"names": _NAMES, "season": {"type": "string"}}, "required": ["names"]},
     compare_players),
    ("injuries", "Injuries from match-day reports: who is injured now, the latest injury, expected return, games "
     "missed in the last N months. For named players, or our_squad=true. Use for 'who's injured', 'is he injury prone'.",
     {"type": "object", "properties": {"names": _NAMES, "our_squad": {"type": "boolean"},
                                       "current_only": {"type": "boolean"}, "months": _INT, "limit": _LIM}},
     injuries),
    ("recent_transfers", "Completed transfers across the market in the last N days (TransferX deals with agreed fees, "
     "and reported transfers elsewhere). Use for 'recent deals for centre-backs', 'what has Arsenal bought'.",
     {"type": "object", "properties": {"position": _POS, "club": {"type": "string"}, "days": _INT,
                                       "min_fee": {"type": "number", "description": "pounds"}, "limit": _LIM}},
     recent_transfers),
    ("comparable_transfers", "What players similar to a named player (same position, similar age) have gone for "
     "recently. Use for 'what should we pay for him', 'what's he worth based on similar deals'.",
     {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}, comparable_transfers),
    ("loans", "The club's loans: players out on loan (and when they return) or in on loan, with fee, wage share, option "
     "or obligation to buy.",
     {"type": "object", "properties": {"direction": {"type": "string", "enum": ["both", "out", "in"]},
                                       "active_only": {"type": "boolean"}, "limit": _LIM}}, loans),
    ("approvals", "The club's spending approvals (PENDING by default): what is asked, by whom, the amount, when it "
     "expires.",
     {"type": "object", "properties": {"status": {"type": "string", "enum": ["PENDING", "APPROVED_EXECUTED",
                                                                            "APPROVED_FAILED", "REJECTED", "EXPIRED", "CANCELLED"]},
                                       "limit": _LIM}}, approvals),
    ("team_activity", "What the club's own people did on TransferX in the last N days (offers, listings, approvals, "
     "deal steps), optionally one person. Use for 'what did the team do this week'.",
     {"type": "object", "properties": {"days": _INT, "person": {"type": "string"}, "limit": _LIM}}, team_activity),
    ("conversation", "The latest messages on one of the club's transfers, by the player's name: what the other club "
     "and the agent last said. Use for 'what did Leeds last say about Bogle'.",
     {"type": "object", "properties": {"player": {"type": "string"}, "limit": _LIM}, "required": ["player"]},
     conversation),
]
