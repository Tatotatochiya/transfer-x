"""Lite mode preferences (docs/feature_spec/lite-mode/BACKEND.md §1)."""
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.lite.models import TextScale, UserPreference



async def role_default(db: AsyncSession, user) -> bool:
    """Lite's default for someone who has never chosen: on for every member
    of a club, owner and staff alike (settings.lite_default_on, product owner
    2026-10-13); never for agents, players or TransferX staff, since Lite is
    for clubs. A choice made in the profile menu or the top bar always wins."""
    if not settings.lite_default_on or getattr(user, "is_superuser", False):
        return False
    if getattr(user, "user_type", None) is None or user.user_type.value != "CLUB":
        return False
    from app.clubs.service import get_club_and_role_for_user

    club, _role = await get_club_and_role_for_user(db, user.id)
    return club is not None


async def get_row(db: AsyncSession, user_id: uuid.UUID) -> UserPreference | None:
    return (await db.execute(select(UserPreference).where(UserPreference.user_id == user_id))).scalar_one_or_none()


async def get_preferences(db: AsyncSession, user) -> dict:
    row = await get_row(db, user.id)
    chosen = row.lite_mode if row is not None else None
    out = {
        "lite_mode": chosen if chosen is not None else await role_default(db, user),
        "lite_mode_is_default": chosen is None,
        "text_scale": row.text_scale if row is not None else TextScale.NORMAL,
    }
    if row is not None:  # no row: the schema's defaults are the column defaults
        out.update({f: getattr(row, f) for f in PUSH_FIELDS})
    return out


# Phone notification settings (mobile notifications §4.1), stored on the same row.
PUSH_FIELDS = (
    "push_your_move", "push_heads_up", "push_summary", "summary_local_time",
    "quiet_hours_enabled", "quiet_start", "quiet_end", "timezone", "push_hide_amounts",
)


async def update_preferences(
    db: AsyncSession, user, *, lite_mode: bool | None = None, text_scale: TextScale | None = None,
    **push_settings,
) -> dict:
    """Set the fields given. Changing Lite mode is audited, so adoption can be
    measured; the text scale is a comfort setting and is not."""
    from app.audit import service as audit_service

    row = await get_row(db, user.id)
    if row is None:
        row = UserPreference(user_id=user.id)
        db.add(row)
    before = row.lite_mode
    if lite_mode is not None:
        row.lite_mode = lite_mode
    if text_scale is not None:
        row.text_scale = text_scale
    for field, value in push_settings.items():
        if field in PUSH_FIELDS and value is not None:
            setattr(row, field, value)
    await db.flush()
    if lite_mode is not None and lite_mode != before:
        await audit_service.emit(
            db, entity_type="user_preferences", entity_id=user.id, action="lite_mode_changed",
            actor_user_id=user.id, payload={"lite_mode": lite_mode, "was": before},
            description=f"Lite mode switched {'on' if lite_mode else 'off'}",
        )
    return await get_preferences(db, user)


# ── Lite home (BACKEND.md §2) ────────────────────────────────────────────────

from datetime import date, datetime, timedelta, timezone  # noqa: E402

RESUME_TTL = timedelta(days=14)
RENEW_WITHIN_DAYS = 180  # the same horizon as the squad context and the Dashboard


def _utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


async def window_state(db: AsyncSession) -> dict:
    """"open", "closed" or "none" (no window configured, so transfers are
    always allowed), with the days until it closes or the next one opens."""
    from app.transfer_window import service as window_service

    now = datetime.now(timezone.utc)
    if not await window_service.any_window_exists(db):
        return {"state": "none"}
    current = await window_service.get_current_window(db)
    if current is not None:
        closes = _utc(current.closes_at)
        return {"state": "open", "closes_at": closes.isoformat(), "days": max(0, (closes - now).days)}
    nxt = await window_service.get_next_window(db)
    if nxt is not None:
        opens = _utc(nxt.opens_at)
        return {"state": "closed", "next_opens_at": opens.isoformat(), "days": max(0, (opens - now).days)}
    return {"state": "closed"}


def _names(clubs: list[str]) -> str:
    if not clubs:
        return ""
    if len(clubs) == 1:
        return f"{clubs[0]} is"
    if len(clubs) == 2:
        return f"{clubs[0]} and {clubs[1]} are"
    return f"{clubs[0]}, {clubs[1]} and {len(clubs) - 2} more are"


def build_tiles(window: dict, waiting: dict, *, renew_count: int, can_market: bool) -> list[dict]:
    """The four home tiles. One place for the rules, so they can change
    without a frontend release (README "Screen 1" and "Screen 2").

    Until a Lite squad picker exists, selling goes to the full-app squad page
    that does the job today; swap the href when it ships.
    """
    no_market = None if can_market else "Your role can't buy or sell players. Ask your club's owner."
    count = waiting["count"]
    offers = {
        "key": "offers", "style": "offers", "title": "Answer offers",
        "subtitle": (_names(waiting["club_names"]) + " waiting for you.") if count else "Nothing waiting",
        "href": "/lite/offers", "badge": f"{count} waiting" if count else None,
    }
    ask = {
        "key": "ask", "style": "ai", "title": "Ask anything",
        "subtitle": "Ask a question in your own words. Get the answer or a shortcut.", "href": "/lite/ask",
    }
    if window["state"] in ("open", "none"):
        return [
            {"key": "buy", "style": "accent", "title": "Buy a player",
             "subtitle": "Search by name, or tell us what you need.",
             "href": "/lite/buy", "disabled_reason": no_market},
            {"key": "sell", "style": "plain", "title": "Sell or loan a player",
             "subtitle": "Pick someone from your squad.", "href": "/club", "disabled_reason": no_market},
            offers,
            ask,
        ]
    renew = {
        "key": "renew", "style": "accent", "title": "Renew contracts",
        "subtitle": (
            "1 player's contract ends this season" if renew_count == 1
            else f"{renew_count} players' contracts end this season" if renew_count
            else "No contracts end in the next six months"
        ),
        "href": "/club",
    }
    plan = {"key": "plan", "style": "plain", "title": "Plan the next window",
            "subtitle": "Make a shortlist before the window opens", "href": "/scouting/shortlists"}
    squad = {"key": "squad", "style": "plain", "title": "My squad",
             "subtitle": "Who's playing, who's on loan", "href": "/club"}
    return [renew, plan, offers if count else squad, ask]


def _cached_briefing_headline(user_id) -> str | None:
    """Today's briefing headline if it has already been produced — never a
    model call from the home screen (CLAUDE.md rule 5)."""
    from app.ai import assist

    prefix = f"briefing:{user_id}:{date.today()}:"
    for key, (_, value) in list(assist._cache.items()):
        if key.startswith(prefix) and isinstance(value, dict):
            return value.get("headline") or None
    return None


async def lite_home(db: AsyncSession, user) -> dict:
    from app.ai.assist import _budget_facts, _contract_ends
    from app.clubs.capabilities import Capability, capabilities_for_role
    from app.clubs.service import get_club_and_role_for_user
    from app.dashboard import service as dashboard_service
    from app.players.models import Player

    club, role = await get_club_and_role_for_user(db, user.id)
    if club is None:
        raise LookupError("No club")
    window = await window_state(db)

    from app.clubs.models import ClubFinance

    budget = await _budget_facts(db, club.id)
    fin = (await db.execute(select(ClubFinance).where(ClubFinance.club_id == club.id))).scalar_one_or_none()
    money = None
    if budget is not None:
        money = {
            "transfer_remaining": budget["transfer_budget_remaining"] or 0,
            "transfer_budget": float(fin.transfer_budget_total) if fin else 0,
            "wage_remaining_weekly": budget["wage_budget_remaining_weekly"] or 0,
            "as_of": datetime.now(timezone.utc).isoformat(),
        }

    # The Dashboard's own list — already masks anonymous buyers.
    items = (await dashboard_service.get_dashboard(db, club=club, current_user=user)).waiting_on_you
    names: list[str] = []
    for i in items:
        if i.club_name and i.club_name not in names:
            names.append(i.club_name)
    waiting = {"count": len(items), "club_names": names}

    squad = (await db.execute(select(Player).where(Player.current_club_id == club.id))).scalars().all()
    ends = await _contract_ends(db, squad)
    horizon = date.today() + timedelta(days=RENEW_WITHIN_DAYS)
    renew_count = sum(1 for p in squad if ends.get(p.id) and ends[p.id] <= horizon)

    can_market = Capability.MARKET_WRITE in capabilities_for_role(role or "OWNER")
    tiles = build_tiles(window, waiting, renew_count=renew_count, can_market=can_market)

    resume = None
    row = await get_row(db, user.id)
    if row is not None and row.lite_resume_json:
        saved = row.lite_resume_json
        try:
            at = datetime.fromisoformat(saved.get("at"))
            if datetime.now(timezone.utc) - _utc(at) <= RESUME_TTL:
                resume = {"title": saved["title"], "href": saved["href"]}
        except (TypeError, ValueError, KeyError):
            resume = None

    return {
        "club_name": club.name,
        "window": window,
        "money": money,
        "waiting": waiting,
        "tiles": tiles,
        "resume": resume,
        "team_contact": None,
        "briefing_headline": _cached_briefing_headline(user.id),
    }


async def set_resume(db: AsyncSession, user, *, title: str, href: str) -> None:
    if not href.startswith("/lite"):
        raise ValueError("Only a Lite page can be resumed")
    row = await get_row(db, user.id)
    if row is None:
        row = UserPreference(user_id=user.id)
        db.add(row)
    row.lite_resume_json = {"title": title[:200], "href": href[:500], "at": datetime.now(timezone.utc).isoformat()}
    await db.flush()


async def clear_resume(db: AsyncSession, user) -> None:
    row = await get_row(db, user.id)
    if row is not None:
        row.lite_resume_json = None
        await db.flush()


# ── Buy flow (BACKEND.md §2a) ────────────────────────────────────────────────

POSITION_WORDS = {"GK": ("goalkeeper", "goalkeepers"), "DEF": ("defender", "defenders"),
                  "MID": ("midfielder", "midfielders"), "FWD": ("forward", "forwards")}
# A squad's usual depth per position, as "Who might want him?" uses.
TYPICAL_DEPTH = {"GK": 3, "DEF": 8, "MID": 8, "FWD": 6}
CONTRACT_DISCOUNT_MONTHS = 12


async def squad_counts(db: AsyncSession, club_id) -> dict[str, int]:
    """Players per position the club owns: under contract to it, or created
    by one of its people and not yet under contract anywhere (the same
    ownership rule listing uses, players.service.get_owning_club_id)."""
    from app.notifications.service import club_member_user_ids
    from app.players.models import Player

    members = await club_member_user_ids(db, club_id)
    rows = (await db.execute(select(Player.position).where(
        (Player.current_club_id == club_id)
        | (Player.current_club_id.is_(None) & Player.created_by_user_id.in_(members))
    ))).scalars().all()
    counts = {k: 0 for k in POSITION_WORDS}
    for pos in rows:
        if pos is not None:
            counts[pos.value] = counts.get(pos.value, 0) + 1
    return counts


async def _prices(db: AsyncSession, players, owned: set | frozenset = frozenset()) -> dict:
    """{player_id: (price, basis, sale)}: an open fixed/offers listing's asking
    price; else the fee model, 30% lower when his contract ends within a year
    (the pricing assistant's rule); a free agent costs nothing. No price → absent."""
    from app.ai.assist import _contract_ends
    from app.players.models import PlayerStatus
    from app.sales.models import Sale, SaleStatus, SaleType
    from app.valuation.service import get_latest_valuations

    ids = [p.id for p in players]
    sales = (await db.execute(
        select(Sale).where(Sale.player_id.in_(ids), Sale.status == SaleStatus.OPEN, Sale.sale_type != SaleType.AUCTION)
    )).scalars().all()
    by_sale = {s.player_id: s for s in sales}
    valuations = await get_latest_valuations(db, ids)
    ends = await _contract_ends(db, players)
    soon = date.today() + timedelta(days=CONTRACT_DISCOUNT_MONTHS * 30)
    out = {}
    for p in players:
        sale = by_sale.get(p.id)
        if p.status == PlayerStatus.FREE_AGENT and p.id not in owned:
            out[p.id] = (0.0, "free agent", None)
        elif sale is not None and sale.asking_price is not None:
            out[p.id] = (float(sale.asking_price), "listed", sale)
        elif p.id in valuations:
            fair = float(valuations[p.id].fair_value)
            if ends.get(p.id) and ends[p.id] <= soon:
                out[p.id] = (fair * 0.7, "model, contract ending", sale)
            else:
                out[p.id] = (fair, "model", sale)
    return out


# The price TransferX shows for a player, shared with the AI player search.
player_prices = _prices


def _pos(p) -> str | None:
    """A player's position code, whether the enum or its string."""
    return getattr(p.position, "value", p.position) if p.position else None


# ── Buy flow search by name ──────────────────────────────────────────────────

SEARCH_LIMIT = 10
SEARCH_POOL = 25
# Where a word of a name can start: "Son", "H. Son", "J.Son", "Wan-Bissaka", "O'Shea".
WORD_STARTS = ("", "% ", "%.", "%-", "%'")
# Then the order results are shown in: players the club can act on first.
SEARCH_ORDER = ("buyable", "offer_in", "free_agent", "in_transfer", "outside", "yours")


async def _resolve_for_club(db: AsyncSession, club, rows) -> list[dict]:
    """Each player as the Buy page shows him: whether the club can make an
    offer for him now and at what price (the same price and ownership rules
    as the bid card), or why not, and whether he is on its shortlist."""
    from app.clubs.models import Club
    from app.deals.service import get_active_deals_for_players
    from app.offers.models import Offer, OfferStatus
    from app.players.models import PlayerStatus
    from app.players.service import get_owning_club_id

    if not rows:
        return []
    ids = [p.id for p in rows]
    owner_of = {p.id: None if p.status == PlayerStatus.EXTERNAL else await get_owning_club_id(db, p) for p in rows}
    busy = await get_active_deals_for_players(db, ids)
    my_offers = dict((await db.execute(
        select(Offer.player_id, Offer.id).where(
            Offer.player_id.in_(ids), Offer.from_club_id == club.id,
            Offer.status.in_([OfferStatus.SENT, OfferStatus.COUNTERED]))
    )).all())
    prices = await _prices(db, [p for p in rows if p.status != PlayerStatus.EXTERNAL],
                           owned={pid for pid, o in owner_of.items() if o is not None})
    club_names = dict((await db.execute(
        select(Club.id, Club.name).where(Club.id.in_({o for o in owner_of.values() if o}))
    )).all())
    shortlisted = await _shortlisted(db, club.id, ids)

    found = []
    for p in rows:
        owner = owner_of[p.id]
        price, basis, _sale = prices.get(p.id, (None, None, None))
        offer_id = None
        if owner == club.id:
            state, note = "yours", "He's already your player."
        elif p.status == PlayerStatus.EXTERNAL or (owner is None and p.status != PlayerStatus.FREE_AGENT):
            state, note = "outside", "His club isn't on TransferX, so there's no one to send an offer to."
        elif p.id in my_offers:
            state, note, offer_id = "offer_in", "You already have an offer in for him.", my_offers[p.id]
        elif p.id in busy and busy[p.id].status.value == "IN_PROGRESS":
            state, note = "in_transfer", "He's already in a transfer with another club."
        elif owner is None:
            state, note = "free_agent", "A free agent: there's no fee to pay."
        else:
            state = "buyable"
            note = None if price is not None else "No price yet: you choose the fee."
        if state == "outside":
            club_label = (p.world_team.name if p.world_team else None) or p.team_name
        elif state == "free_agent":
            club_label = None
        else:
            club_label = club_names.get(owner)
        found.append({
            "player_id": str(p.id), "name": p.name, "photo_url": p.photo_url, "age": p.age, "position": _pos(p),
            "club": club_label, "state": state,
            "price": price if state in ("buyable", "free_agent") else None,
            "price_basis": basis if state in ("buyable", "free_agent") else None,
            "offer_id": str(offer_id) if offer_id else None, "note": note,
            "shortlisted": p.id in shortlisted,
        })
    return found


async def _shortlisted(db: AsyncSession, club_id, player_ids) -> set:
    from app.scouting.models import Shortlist, ShortlistItem

    return set((await db.execute(
        select(ShortlistItem.player_id).join(Shortlist, Shortlist.id == ShortlistItem.shortlist_id)
        .where(Shortlist.club_id == club_id, ShortlistItem.player_id.in_(player_ids))
    )).scalars())


async def _club(db: AsyncSession, user):
    from app.clubs.service import get_club_and_role_for_user

    club, _ = await get_club_and_role_for_user(db, user.id)
    if club is None:
        raise LookupError("No club")
    return club


async def buy_search(db: AsyncSession, user, *, q: str) -> dict:
    """Players by name for the Buy page's search box, each resolved as
    `_resolve_for_club` does. Every player the club may see is found, with
    the reason when he can't be bought: a name that finds nothing looks like
    a broken search. No model call."""
    import re

    from sqlalchemy import case, or_
    from sqlalchemy.orm import selectinload

    from app.players.models import Player, PlayerVisibility

    club = await _club(db, user)
    term = q.strip()
    if len(term) < 2:
        raise ValueError("Type at least two letters")
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    rows = (await db.execute(
        select(Player)
        .where(Player.name.ilike(f"%{escaped}%", escape="\\"),
               (Player.visibility != PlayerVisibility.PRIVATE) | (Player.current_club_id == club.id))
        .options(selectinload(Player.world_team))
        .order_by(case((or_(*(Player.name.ilike(f"{lead}{escaped}%", escape="\\") for lead in WORD_STARTS)), 0),
                       else_=1), Player.name)
        .limit(SEARCH_POOL)
    )).scalars().all()
    found = await _resolve_for_club(db, club, rows)
    # A word of his name starting with the search ("son" finds "H. Son" before
    # "A. Harrison"), then the players the club can act on; name order within.
    word = re.compile(r"(^|[\s.'-])" + re.escape(term.lower()))
    found.sort(key=lambda r: (0 if word.search(r["name"].lower()) else 1, SEARCH_ORDER.index(r["state"])))
    return {"q": term, "players": found[:SEARCH_LIMIT]}


# ── The club's targets: its shortlists and the players it is interested in ──

TARGETS_LIMIT = 50
LITE_SHORTLIST = "Shortlist"  # where Lite's "Shortlist" button puts a player


async def buy_targets(db: AsyncSession, user) -> dict:
    """The players the club is already after: on any of its shortlists, or
    marked as of interest (the same set as Scouting's targets). Each is
    resolved as the search does, players the club can act on first. Its own
    players are left out. No model call."""
    from sqlalchemy.orm import selectinload

    from app.players.models import Player, PlayerVisibility
    from app.scouting.models import PlayerInterest, Shortlist, ShortlistItem

    club = await _club(db, user)
    listed = (await db.execute(
        select(ShortlistItem.player_id, Shortlist.name).join(Shortlist, Shortlist.id == ShortlistItem.shortlist_id)
        .where(Shortlist.club_id == club.id).order_by(Shortlist.name)
    )).all()
    interested = (await db.execute(
        select(PlayerInterest.player_id).where(PlayerInterest.club_id == club.id)
    )).scalars().all()
    lists_of: dict = {}
    for pid, name in listed:
        lists_of.setdefault(pid, []).append(name)
    ids = set(lists_of) | set(interested)
    if not ids:
        return {"players": [], "total": 0}
    rows = (await db.execute(
        select(Player).where(Player.id.in_(ids),
                             (Player.visibility != PlayerVisibility.PRIVATE) | (Player.current_club_id == club.id))
        .options(selectinload(Player.world_team)).order_by(Player.name)
    )).scalars().all()
    found = [r for r in await _resolve_for_club(db, club, rows) if r["state"] != "yours"]
    for r in found:
        r["on_shortlists"] = lists_of.get(uuid.UUID(r["player_id"]), [])
    found.sort(key=lambda r: SEARCH_ORDER.index(r["state"]))
    return {"players": found[:TARGETS_LIMIT], "total": len(found)}


async def shortlist_add(db: AsyncSession, user, player_id: uuid.UUID) -> None:
    """Lite's "Shortlist" button: put the player on the club's shortlist
    called "Shortlist", made if the club has none by that name. A player
    already on any of its shortlists stays as he is. Caller commits."""
    from app.players.models import Player, PlayerVisibility
    from app.scouting import service as scouting

    club = await _club(db, user)
    player = await db.get(Player, player_id)
    if player is None or (player.visibility == PlayerVisibility.PRIVATE and player.current_club_id != club.id):
        raise LookupError("Player not found")
    if await _shortlisted(db, club.id, [player_id]):
        return
    from app.scouting.models import Shortlist

    sl = (await db.execute(
        select(Shortlist).where(Shortlist.club_id == club.id, Shortlist.name == LITE_SHORTLIST)
    )).scalar_one_or_none()
    if sl is None:
        sl = await scouting.create_shortlist(db, club_id=club.id, name=LITE_SHORTLIST)
    await scouting.add_to_shortlist(db, shortlist_id=sl.id, player_id=player_id)


async def shortlist_remove(db: AsyncSession, user, player_id: uuid.UUID) -> int:
    """Take the player off every one of the club's shortlists: in Lite there
    is one shortlist, so "take him off" means off it everywhere. Interest
    marked in Scouting stays. Returns how many lists he was on. Caller commits."""
    from sqlalchemy import delete

    from app.scouting.models import Shortlist, ShortlistItem

    club = await _club(db, user)
    result = await db.execute(delete(ShortlistItem).where(
        ShortlistItem.player_id == player_id,
        ShortlistItem.shortlist_id.in_(select(Shortlist.id).where(Shortlist.club_id == club.id)),
    ))
    return result.rowcount or 0


# ── Action cards (L4, README "Screen 5") ────────────────────────────────────
#
# The card is the "normal confirmed form" of ADR 0006: these endpoints only
# describe it. Confirming calls the existing offer endpoints, and the money
# panel comes from POST /ai/offer-check, so no figure here is final.

HALF_M = 500_000
NO_MARKET_REASON = "Your role can't send or answer offers. Ask your club's owner."


def _round_half_m(v: float, *, up: bool = False, down: bool = False) -> float:
    """To the nearest £0.5m (or up/down to it); never below £0.5m."""
    import math

    steps = v / HALF_M
    steps = math.ceil(steps) if up else math.floor(steps) if down else round(steps)
    return float(max(1, steps) * HALF_M)


def _contract_years(age: int | None) -> int:
    """A usual first contract for his age: long for the young, short late on."""
    if age is None or age <= 29:
        return 4
    return 3 if age <= 31 else 2


async def _can_market(db: AsyncSession, user, role: str | None) -> bool:
    from app.clubs.capabilities import Capability, capabilities_for_role

    return bool(user.is_superuser) or Capability.MARKET_WRITE in capabilities_for_role(role or "OWNER")


async def offer_draft(db: AsyncSession, user, *, player_id: uuid.UUID) -> dict:
    """What a new bid's card starts from: the player, the club that would
    answer, a starting fee (the asking price, else the fee model, as the buy
    results show it) rounded to £0.5m, his current wage, and a usual contract
    length. `disabled_reason` says why the club can't send it now, if so."""
    from app.clubs.models import Club
    from app.clubs.service import get_club_and_role_for_user
    from app.deals.service import get_active_deal_for_player
    from app.offers.service import get_active_offer_for_buyer
    from app.players.models import Contract, PlayerStatus
    from app.players.service import get_owning_club_id, get_player_by_id
    from app.transfer_window.service import is_transfer_allowed

    club, role = await get_club_and_role_for_user(db, user.id)
    if club is None:
        raise LookupError("No club")
    player = await get_player_by_id(db, player_id)
    if player is None:
        raise LookupError("Player not found")
    owner = await get_owning_club_id(db, player)
    if owner == club.id:
        raise ValueError("He is already your player.")
    if owner is None:
        if player.status == PlayerStatus.FREE_AGENT:
            raise ValueError("He is a free agent, so there is no club to make an offer to. Sign him from his page.")
        raise ValueError("He plays for a club that is not on TransferX, so no one could answer an offer.")

    prices = await _prices(db, [player], owned={player.id})
    price, basis, sale = prices.get(player.id, (None, None, None))
    wage = (await db.execute(
        select(Contract.wage_weekly).where(Contract.player_id == player.id, Contract.is_active.is_(True))
    )).scalars().first()
    seller_name = (await db.execute(select(Club.name).where(Club.id == owner))).scalar_one_or_none()

    disabled = None
    existing = await get_active_offer_for_buyer(db, player.id, club.id)
    deal = await get_active_deal_for_player(db, player.id)
    if not await _can_market(db, user, role):
        disabled = NO_MARKET_REASON
    elif not user.is_superuser and not await is_transfer_allowed(db):
        disabled = "The transfer window is closed, so offers can't be sent until it opens."
    elif existing is not None:
        disabled = "You already have an offer in for him."
    elif deal is not None and deal.status == "IN_PROGRESS":
        disabled = "He is already in a transfer with another club."

    return {
        "player_id": str(player.id), "name": player.name, "age": player.age, "position": _pos(player),
        "to_club_id": str(owner), "to_club_name": seller_name,
        "sale_id": str(sale.id) if sale is not None else None,
        "fee": _round_half_m(price) if price else None,
        "fee_basis": basis,
        "asking_price": float(sale.asking_price) if sale is not None and sale.asking_price is not None else None,
        "wage_weekly": float(wage) if wage is not None else None,
        "contract_years": _contract_years(player.age),
        "existing_offer_id": str(existing.id) if existing is not None else None,
        "disabled_reason": disabled,
    }


async def offer_card(db: AsyncSession, user, *, offer_id: uuid.UUID) -> dict:
    """An offer the club is party to, as an action card: who it's with (an
    anonymous buyer stays masked), its terms, whether it's the club's move,
    and a counter to start from. Only a permanent offer is countered in Lite;
    a loan's terms are changed in the full app."""
    from sqlalchemy.orm import selectinload

    from app.ai.assist import _masked
    from app.clubs.service import get_club_and_role_for_user
    from app.offers.models import Offer, OfferStatus
    from app.valuation.service import get_latest_valuations

    club, role = await get_club_and_role_for_user(db, user.id)
    if club is None:
        raise LookupError("No club")
    offer = (await db.execute(
        select(Offer).where(Offer.id == offer_id).options(
            selectinload(Offer.from_club), selectinload(Offer.to_club), selectinload(Offer.player))
    )).scalar_one_or_none()
    if offer is None or club.id not in (offer.from_club_id, offer.to_club_id):
        raise LookupError("Offer not found")

    side = "buyer" if offer.from_club_id == club.id else "seller"
    if side == "buyer":
        other = offer.to_club.name if offer.to_club else "the selling club"
    elif _masked(offer, club.id):
        league = offer.from_club.masking_league if offer.from_club else None
        other = f"an undisclosed {league} club" if league else "an undisclosed club"
    else:
        other = offer.from_club.name if offer.from_club else "the buying club"

    loan = getattr(offer.deal_type, "value", offer.deal_type) == "LOAN"
    fee = float((offer.loan_fee if loan else offer.fee_amount) or 0)
    open_ = offer.status in (OfferStatus.SENT, OfferStatus.COUNTERED)
    your_move = open_ and offer.last_actor_club_id != club.id

    # The selling club's own valuation of its player: confidential, so only
    # on the seller's card (the holding club's contract; contract_for_viewer).
    valuation = None
    if side == "seller":
        from app.players.models import Contract

        v = (await db.execute(select(Contract.club_valuation).where(
            Contract.player_id == offer.player_id, Contract.club_id == club.id, Contract.is_active.is_(True),
        ))).scalars().first()
        valuation = float(v) if v is not None else None

    counter = None
    if your_move and not loan:
        if side == "seller" and valuation and valuation > fee:
            # The club has said what he's worth: ask for that (the push's
            # "Ask for £21m" opens this card with the same figure).
            counter = valuation
        elif side == "seller":
            anchors = [fee * 1.1]
            vals = await get_latest_valuations(db, [offer.player_id])
            if offer.player_id in vals:
                anchors.append(float(vals[offer.player_id].fair_value))
            price = await _prices(db, [offer.player], owned={offer.player_id})
            if offer.player_id in price and price[offer.player_id][1] == "listed":
                anchors.append(price[offer.player_id][0])
            counter = _round_half_m(max(anchors), up=True)
        elif fee > HALF_M:
            counter = _round_half_m(fee * 0.95, down=True)
        if counter is not None and counter == fee:
            counter = fee + HALF_M if side == "seller" else max(HALF_M, fee - HALF_M)

    disabled = None
    if not await _can_market(db, user, role):
        disabled = NO_MARKET_REASON
    elif not open_:
        disabled = f"This offer has been {offer.status.value.lower()}, so there is nothing to answer."
    elif not your_move:
        disabled = f"Waiting for {other} to reply."

    return {
        "offer_id": str(offer.id),
        "side": side,
        "status": offer.status.value,
        "player_id": str(offer.player_id),
        "player_name": offer.player.name if offer.player else None,
        "player_photo_url": offer.player.photo_url if offer.player else None,
        "other_club": other,
        "deal_type": "LOAN" if loan else "PERMANENT",
        "fee": fee,
        "wage_weekly": float(offer.wage_weekly) if offer.wage_weekly is not None else None,
        "wage_split_pct": float(offer.wage_split_pct) if offer.wage_split_pct is not None else None,
        "contract_years": offer.contract_years,
        "loan_start": offer.loan_start.isoformat() if offer.loan_start else None,
        "loan_end": offer.loan_end.isoformat() if offer.loan_end else None,
        "has_add_ons": bool(offer.clauses or offer.add_ons or offer.instalments or offer.sell_on_pct),
        "your_move": your_move,
        "counter_suggestion": counter,
        "disabled_reason": disabled,
        "expires_at": offer.expires_at.isoformat() if offer.expires_at else None,
        "your_valuation": valuation,
    }


# ── Ask anything suggestions (L5, README "Screen 4") ─────────────────────────

_POSITION_WORD = {"GK": "goalkeeper", "DEF": "defender", "MID": "midfielder", "FWD": "forward"}


async def ask_suggestions(db: AsyncSession, user) -> list[str]:
    """Four questions worth tapping, from the club's own state; no model call.
    An offer waiting on the club comes first, then its thinnest position at a
    price it can afford, then money and the day's to-do."""
    from app.ai.assist import _budget_facts
    from app.clubs.service import get_club_and_role_for_user
    from app.offers.models import Offer, OfferStatus
    from sqlalchemy.orm import selectinload

    club, _ = await get_club_and_role_for_user(db, user.id)
    if club is None:
        raise LookupError("No club")
    out: list[str] = []
    waiting = (await db.execute(
        select(Offer).where(Offer.to_club_id == club.id, Offer.status.in_([OfferStatus.SENT, OfferStatus.COUNTERED]),
                            (Offer.last_actor_club_id.is_(None)) | (Offer.last_actor_club_id != club.id))
        .options(selectinload(Offer.player)).order_by(Offer.last_action_at.desc()).limit(1)
    )).scalars().first()
    if waiting is not None and waiting.player is not None:
        out.append(f"What's happening with {waiting.player.name}?")
    counts = await squad_counts(db, club.id)
    thinnest = min(_POSITION_WORD, key=lambda p: counts.get(p, 0) - TYPICAL_DEPTH.get(p, 6))
    budget = await _budget_facts(db, club.id) or {}
    room = budget.get("transfer_budget_remaining") or 0
    price = "under £10m" if room >= 10_000_000 else "under £5m" if room >= 5_000_000 else "on a free or a loan"
    out.append(f"Find me a {_POSITION_WORD[thinnest]} {price}")
    out.append("How much can we still spend?")
    out.append("What needs me today?")
    return out[:4]
