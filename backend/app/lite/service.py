"""Lite mode preferences (docs/feature_spec/lite-mode/BACKEND.md §1)."""
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.lite.models import TextScale, UserPreference

# Roles Lite is meant for: people who decide rather than operate the software.
LITE_DEFAULT_ROLES = frozenset({"OWNER", "SPORTING_DIRECTOR"})


async def role_default(db: AsyncSession, user) -> bool:
    """Lite's default for someone who has never chosen. Off for everyone until
    the role default is switched on (settings.lite_role_default_on, after L4);
    then on for a club's owner and sporting directors only — never for agents,
    players or TransferX staff."""
    if not settings.lite_role_default_on:
        return False
    if getattr(user, "user_type", None) is None or user.user_type.value != "CLUB":
        return False
    from app.clubs.service import get_club_and_role_for_user

    club, role = await get_club_and_role_for_user(db, user.id)
    return club is not None and role in LITE_DEFAULT_ROLES


async def get_row(db: AsyncSession, user_id: uuid.UUID) -> UserPreference | None:
    return (await db.execute(select(UserPreference).where(UserPreference.user_id == user_id))).scalar_one_or_none()


async def get_preferences(db: AsyncSession, user) -> dict:
    row = await get_row(db, user.id)
    chosen = row.lite_mode if row is not None else None
    return {
        "lite_mode": chosen if chosen is not None else await role_default(db, user),
        "lite_mode_is_default": chosen is None,
        "text_scale": row.text_scale if row is not None else TextScale.NORMAL,
    }


async def update_preferences(
    db: AsyncSession, user, *, lite_mode: bool | None = None, text_scale: TextScale | None = None,
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
             "subtitle": "Tell us what you need. We'll find them.",
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


# ── Buy flow candidates (BACKEND.md §2a, decision 3) ─────────────────────────

POSITION_WORDS = {"GK": ("goalkeeper", "goalkeepers"), "DEF": ("defender", "defenders"),
                  "MID": ("midfielder", "midfielders"), "FWD": ("forward", "forwards")}
BANDS = {"0-5": (0, 5_000_000), "5-10": (5_000_000, 10_000_000), "10-20": (10_000_000, 20_000_000)}
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


def _in_band(price: float, band: str, *, loanable: bool, free_agent: bool) -> bool:
    if band == "free":
        return free_agent or loanable
    low, high = BANDS[band]
    return low <= price <= high if low == 0 else low < price <= high


def _pos(p) -> str | None:
    """A player's position code, whether the enum or its string."""
    return getattr(p.position, "value", p.position) if p.position else None


def _plain_reason(p, *, pos_count: int, price: float, basis: str) -> str:
    word = POSITION_WORDS.get(_pos(p) or "", ("player", "players"))
    have = "no" if pos_count == 0 else str(pos_count)
    bits = [f"You have {have} {word[1] if pos_count != 1 else word[0]}"]
    if p.age:
        bits.append(f"he's {p.age}")
    if basis == "free agent":
        bits.append("and a free agent")
    else:
        bits.append(f"and {'listed at' if basis == 'listed' else 'valued at'} {_money(price)}")
    return ", ".join(bits[:-1]) + " " + bits[-1] + "." if len(bits) > 1 else bits[0] + "."


def _money(v: float) -> str:
    if v >= 1_000_000:
        m = round(v / 1_000_000, 1)
        return f"£{int(m) if m == int(m) else m}m"
    return f"£{round(v / 1000)}k"


async def buy_candidates(db: AsyncSession, user, *, position: str, band: str) -> dict:
    """Three players the club could make an offer for now, picked in code.
    The model only rewords the reasons, if it is available and the user's
    allowance allows; otherwise the plain reasons stand."""
    from app.ai import assist
    from app.clubs.service import get_club_and_role_for_user
    from app.deals.service import get_active_deals_for_players
    from app.players.models import Contract, Player, PlayerPosition, PlayerStatus

    club, _ = await get_club_and_role_for_user(db, user.id)
    if club is None:
        raise LookupError("No club")
    if position not in ("GK", "DEF", "MID", "FWD", "ANY") or band not in (*BANDS, "free"):
        raise ValueError("Unknown position or budget")
    counts = await squad_counts(db, club.id)

    q = select(Player).where(
        Player.status.in_([PlayerStatus.CONTRACTED, PlayerStatus.FREE_AGENT]),
        (Player.current_club_id.is_(None)) | (Player.current_club_id != club.id),
    )
    if position != "ANY":
        q = q.where(Player.position == PlayerPosition(position))
    pool = (await db.execute(q)).scalars().all()
    # A player with no club on record may still be a club's: one it created
    # and has not put under contract. Resolve him as listing does, so a club
    # is never offered its own man as a "free agent".
    from app.players.service import get_owning_club_id

    owner_of: dict = {}
    for p in pool:
        if p.current_club_id is None:
            owner_of[p.id] = await get_owning_club_id(db, p)
    pool = [p for p in pool if owner_of.get(p.id) != club.id]
    busy = await get_active_deals_for_players(db, [p.id for p in pool])
    pool = [p for p in pool if not (p.id in busy and busy[p.id].status.value == "IN_PROGRESS")]
    prices = await _prices(db, pool, owned={pid for pid, o in owner_of.items() if o is not None})

    wages = dict((await db.execute(
        select(Contract.player_id, Contract.wage_weekly).where(
            Contract.player_id.in_([p.id for p in pool]), Contract.is_active.is_(True))
    )).all())

    ranked = []
    for p in pool:
        if p.id not in prices:
            continue  # no price at all: nothing to offer against
        price, basis, sale = prices[p.id]
        loanable = sale is not None and getattr(sale.availability, "value", sale.availability) in ("LOAN", "EITHER")
        if not _in_band(price, band, loanable=loanable, free_agent=basis == "free agent"):
            continue
        pos = _pos(p)
        need = max(0, TYPICAL_DEPTH.get(pos, 6) - counts.get(pos, 0)) if pos else 0
        age_fit = -abs((p.age or 26) - 25)
        ranked.append((need, 1 if basis == "listed" else 0, age_fit, -price, p, price, basis, sale))
    ranked.sort(key=lambda r: r[:4], reverse=True)
    top = ranked[:3]

    from app.clubs.models import Club

    club_of = {r[4].id: r[4].current_club_id or owner_of.get(r[4].id) for r in top}
    club_names = dict((await db.execute(
        select(Club.id, Club.name).where(Club.id.in_([c for c in club_of.values() if c]))
    )).all()) if top else {}
    players = []
    for need, _, _, _, p, price, basis, sale in top:
        pos = _pos(p)
        players.append({
            "player_id": str(p.id), "name": p.name, "age": p.age, "position": pos,
            "club": club_names.get(club_of.get(p.id)),
            "free_agent": basis == "free agent",
            "price": price, "price_basis": basis, "sale_id": str(sale.id) if sale else None,
            "wage_weekly": float(wages[p.id]) if wages.get(p.id) is not None else None,
            "reason": _plain_reason(p, pos_count=counts.get(pos, 0) if pos else 0, price=price, basis=basis),
        })

    # The model may reword the reasons; results never wait on it.
    if players and assist.ai_available():
        facts = {"club": club.name, "squad_counts_by_position": counts, "players": [
            {k: v for k, v in pl.items() if k in ("player_id", "name", "age", "position", "club", "price", "price_basis", "reason")}
            for pl in players]}
        key = f"lite-buy:{club.id}:{position}:{band}:{date.today()}:{','.join(pl['player_id'] for pl in players)}"

        async def produce():
            data = await assist._llm_json("LITE_BUY_REASONS_USER", user_id=user.id, endpoint="lite-buy-reasons",
                                          max_tokens=500, facts_json=assist._dumps(facts))
            return data.get("reasons") if isinstance(data.get("reasons"), dict) else {}

        try:
            reasons, _ = await assist._cached(key, produce)
            for pl in players:
                text = str(reasons.get(pl["player_id"], "")).strip()
                if 0 < len(text) <= 200:
                    pl["reason"] = text
        except Exception:
            pass  # rate limit, no model, bad output: the plain reasons stand

    return {"position": position, "band": band, "squad_counts": counts, "players": players}


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

    counter = None
    if your_move and not loan:
        if side == "seller":
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
