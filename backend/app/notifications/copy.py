"""What a push says (docs/feature_spec/mobile-notifications §3.2).

Each builder returns the keyword arguments `create_notification` and
`notify_club` take for a push: `title`, `body`, `group_key`, `deadline_at`
and up to two `actions`. The in-app `message` stays as it was (email uses it).

- Money is written the way the app writes it: £18m, £19.5m, £850k.
- A buyer is named through app.common.masking, so an anonymous one stays
  "A Premier League club" until the offer is accepted.
- Deadlines are written per recipient, in their own timezone, when the push
  is sent or the list is read: a title or body holds the tokens DEADLINE
  ("today 18:00", "tomorrow 09:30", "Wed 18:00", or "9 Oct" beyond
  six days) and TIME_LEFT ("5 hours left"),
  and `render` fills them in.
- An action only opens a page (ADR 0006). Counter and accept open the Lite
  offer card with that action chosen; the card still asks before sending.
"""
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.masking import buyer_name

DEADLINE = "{deadline}"
TIME_LEFT = "{time_left}"   # "5 hours left"
TIME_REMAINING = "{time_remaining}"  # "5 hours"
_TOKENS = (DEADLINE, TIME_LEFT, TIME_REMAINING)


def money(value) -> str:
    """£18m, £19.5m, £850k, £900."""
    v = Decimal(str(value))
    if v >= 1_000_000:
        return f"£{(v / 1_000_000):.1f}".rstrip("0").rstrip(".") + "m"
    if v >= 1_000:
        return f"£{round(v / 1_000)}k"
    return f"£{v:,.0f}"


def render(text: str | None, deadline_at: datetime | None, tz: ZoneInfo, now: datetime) -> str | None:
    """Fill in DEADLINE and TIME_LEFT for one recipient."""
    if text is None or not any(t in text for t in _TOKENS):
        return text
    if deadline_at is None:
        return text.replace(DEADLINE, "soon").replace(TIME_LEFT, "little time left").replace(TIME_REMAINING, "a short while")
    deadline = deadline_at if deadline_at.tzinfo else deadline_at.replace(tzinfo=timezone.utc)
    local = deadline.astimezone(tz)
    # A weekday alone is ambiguous a week out ("Fri" on a Friday reads as
    # tonight), so: today, tomorrow, a weekday within six days, else the date.
    days_away = (local.date() - now.astimezone(tz).date()).days
    if days_away == 0:
        when = f"today {local:%H:%M}"
    elif days_away == 1:
        when = f"tomorrow {local:%H:%M}"
    elif 1 < days_away < 6:
        when = f"{local:%a %H:%M}"
    else:
        when = f"{local.day} {local:%b}"
    left = deadline - now
    if left <= timedelta(0):
        remaining = "no time"
    elif left < timedelta(hours=1):
        minutes = max(1, int(left.total_seconds() // 60))
        remaining = f"{minutes} minute{'s' if minutes != 1 else ''}"
    elif left < timedelta(hours=24):
        hours = int(left.total_seconds() // 3600)
        remaining = f"{hours} hour{'s' if hours != 1 else ''}"
    else:
        days = left.days
        remaining = f"{days} day{'s' if days != 1 else ''}"
    return text.replace(DEADLINE, when).replace(TIME_LEFT, f"{remaining} left").replace(TIME_REMAINING, remaining)


def _sentence_start(text: str) -> str:
    return text[:1].upper() + text[1:]


# ── Offers ────────────────────────────────────────────────────────────────────


async def _offer_facts(db: AsyncSession, offer):
    from app.clubs.models import Club
    from app.players.models import Player

    player = (await db.execute(select(Player.name).where(Player.id == offer.player_id))).scalar_one_or_none()
    buyer = await db.get(Club, offer.from_club_id) if offer.from_club_id else None
    seller = await db.get(Club, offer.to_club_id) if offer.to_club_id else None
    return player or "a player", buyer, seller


def offer_amount(offer) -> tuple[Decimal | None, str]:
    """The headline figure and what kind of offer it is."""
    from app.deals.models import DealType

    if offer.deal_type == DealType.LOAN:
        return (offer.loan_fee, "loan offer")
    if offer.deal_type == DealType.PRE_CONTRACT:
        return (None, "pre-contract offer")
    if offer.deal_type == DealType.FREE_TRANSFER or not offer.fee_amount:
        return (None, "free-transfer offer")
    return (offer.fee_amount, "offer")


def _can_counter_in_lite(offer) -> bool:
    """The Lite card counters permanent fees only (loans in the full app)."""
    from app.deals.models import DealType

    return offer.deal_type == DealType.PERMANENT and bool(offer.fee_amount)


async def offer_received(db: AsyncSession, offer) -> dict:
    """For the selling club. Names the buyer only if the buyer isn't hidden,
    and the club's own valuation, which only it can see."""
    from app.players.models import Contract

    player, buyer, seller = await _offer_facts(db, offer)
    amount, kind = offer_amount(offer)
    who = buyer_name(offer, buyer, offer.to_club_id)
    title = f"{_sentence_start(kind)} for {player}" + (f": {money(amount)}" if amount else "")

    valuation = None
    if offer.to_club_id:
        valuation = (await db.execute(select(Contract.club_valuation).where(
            Contract.player_id == offer.player_id, Contract.club_id == offer.to_club_id, Contract.is_active.is_(True),
        ))).scalars().first()
    parts = [who]
    if valuation:
        parts.append(f"your valuation {money(valuation)}")
    if offer.expires_at:
        parts.append(f"reply by {DEADLINE}")

    actions = []
    if valuation and amount and Decimal(valuation) > Decimal(amount) and _can_counter_in_lite(offer):
        actions.append({
            "action": "counter", "title": f"Ask for {money(valuation)}",
            # The offer page: a phone goes on to the Lite card with this
            # counter ready, a wider screen opens the counter form filled in.
            "url": f"/offers/{offer.id}?action=counter&amount={int(Decimal(valuation))}",
        })
    actions.append({"action": "open", "title": "Open", "url": f"/offers/{offer.id}"})
    return {
        "title": title, "body": " · ".join(parts), "group_key": f"offer:{offer.id}",
        "deadline_at": offer.expires_at, "actions": actions,
    }


async def offer_countered(db: AsyncSession, offer, *, recipient_club_id, previous: Decimal | None, raised: bool = False) -> dict:
    """For the club whose move it now is. `previous` is the figure before
    this counter; `raised` is the buyer improving its own offer."""
    player, buyer, seller = await _offer_facts(db, offer)
    amount, _kind = offer_amount(offer)
    recipient_is_seller = str(recipient_club_id) == str(offer.to_club_id)
    other = buyer_name(offer, buyer, recipient_club_id) if recipient_is_seller else (seller.name if seller else "The seller")

    if raised:
        title = f"{other} raised their offer" + (f" to {money(amount)}" if amount else "")
    else:
        title = f"{other} countered" + (f" at {money(amount)}" if amount else "")
    parts = [player]
    if amount and previous and Decimal(previous) != Decimal(amount):
        parts.append(f"{'up' if Decimal(amount) > Decimal(previous) else 'down'} from {money(previous)}")
    if offer.expires_at:
        parts.append(f"{TIME_LEFT} to reply")

    actions = []
    if amount and _can_counter_in_lite(offer):
        actions.append({"action": "accept", "title": f"Accept {money(amount)}",
                        "url": f"/offers/{offer.id}?action=accept"})
    actions.append({"action": "open", "title": "Open", "url": f"/offers/{offer.id}"})
    return {
        "title": title, "body": " · ".join(parts), "group_key": f"offer:{offer.id}",
        "deadline_at": offer.expires_at, "actions": actions,
    }


async def offer_message(db: AsyncSession, offer, *, sender_club_id, text: str) -> dict:
    """A message on an offer, from the other club (masked if it is the
    hidden buyer)."""
    player, buyer, seller = await _offer_facts(db, offer)
    if str(sender_club_id) == str(offer.from_club_id):
        recipient = offer.to_club_id
        sender = buyer_name(offer, buyer, recipient)
    else:
        sender = seller.name if seller else "The seller"
    return {
        "title": f"{sender} · {player}", "body": _snippet(text), "group_key": f"offer:{offer.id}",
        "actions": [{"action": "reply", "title": "Reply", "url": f"/offers/{offer.id}"}],
    }


def _snippet(text: str, limit: int = 120) -> str:
    one_line = " ".join((text or "").split())
    return one_line if len(one_line) <= limit else one_line[: limit - 1].rstrip() + "…"


# ── Negotiations (deal threads) ───────────────────────────────────────────────


def negotiation_message(*, deal_id, sender: str, role: str | None, text: str) -> dict:
    return {
        "title": f"{sender} ({role})" if role else sender,
        "body": _snippet(text),
        "group_key": f"deal:{deal_id}",
        "actions": [{"action": "reply", "title": "Reply", "url": f"/deals/{deal_id}"}],
    }


# ── Auctions ──────────────────────────────────────────────────────────────────


def auction_ending(*, sale, player: str, seller_view: bool, best: Decimal | None, bids: int, own_bid: Decimal | None) -> dict:
    """An hour or less left. The seller sees the best bid and how many there
    are; a bidder sees its own bid against the best, never who made it."""
    title = f"{_sentence_start(TIME_LEFT)} on the {player} auction"
    if seller_view:
        body = (f"Highest bid {money(best)} · {bids} bid{'s' if bids != 1 else ''}" if best else "No bids yet")
    else:
        body = f"Your bid {money(own_bid)}" + (f" · highest {money(best)}" if best else "") if own_bid else (
            f"Highest bid {money(best)}" if best else None)
    return {
        "title": title, "body": body, "group_key": f"sale:{sale.id}", "deadline_at": sale.deadline,
        "actions": [{"action": "open", "title": "Open", "url": f"/sales/{sale.id}"}],
    }


def outbid(*, sale, player: str, best: Decimal, next_bid: Decimal) -> dict:
    """The rival isn't named: bidders see the book anonymised."""
    parts = [f"Highest bid now {money(best)}"]
    if sale.deadline:
        parts.append(f"ends in {TIME_REMAINING}")
    return {
        "title": f"You've been outbid on {player}",
        "body": " · ".join(parts),
        "group_key": f"sale:{sale.id}",
        "deadline_at": sale.deadline,
        "actions": [
            {"action": "bid", "title": f"Bid {money(next_bid)}", "url": f"/sales/{sale.id}?bid={int(next_bid)}"},
            {"action": "open", "title": "Open", "url": f"/sales/{sale.id}"},
        ],
    }


# ── Approvals ─────────────────────────────────────────────────────────────────


async def approval_player(db: AsyncSession, approval) -> tuple[uuid.UUID | None, str | None, str | None]:
    """The player an approval is about (id, name, photo), from its payload."""
    from app.offers.models import Offer
    from app.players.models import Player
    from app.sales.models import Sale

    payload = approval.payload_json or {}
    player_id = payload.get("player_id")
    if not player_id and payload.get("sale_id"):
        player_id = (await db.execute(select(Sale.player_id).where(Sale.id == uuid.UUID(str(payload["sale_id"]))))).scalar_one_or_none()
    if not player_id and payload.get("offer_id"):
        player_id = (await db.execute(select(Offer.player_id).where(Offer.id == uuid.UUID(str(payload["offer_id"]))))).scalar_one_or_none()
    if not player_id:
        return None, None, None
    row = (await db.execute(select(Player.name, Player.photo_url).where(Player.id == uuid.UUID(str(player_id))))).first()
    return uuid.UUID(str(player_id)), (row[0] if row else None), (row[1] if row else None)


async def approval_requested(db: AsyncSession, approval, club) -> dict:
    """What the approver is being asked, who asked, and the budget after."""
    from app.approvals.models import ApprovalActionType as A
    from app.auth.models import User
    from app.clubs.models import ClubFinance, ClubStaff

    player = (await approval_player(db, approval))[1]

    amount = money(approval.amount)
    of = f" for {player}" if player else ""
    title = {
        A.PLACE_BID: f"Approve a {amount} bid{of}?",
        A.CREATE_OFFER: f"Approve a {amount} offer{of}?",
        A.ACCEPT_OFFER: f"Approve accepting {amount}{of}?",
        A.ACCEPT_BID: f"Approve accepting a {amount} bid{of}?",
        A.EXERCISE_OPTION: f"Approve exercising the option{of} ({amount})?",
    }.get(approval.action_type, approval.summary or "An approval needs you")

    requester = await db.get(User, approval.requested_by_user_id)
    role = (await db.execute(select(ClubStaff.role).where(
        ClubStaff.club_id == club.id, ClubStaff.user_id == approval.requested_by_user_id,
    ))).scalar_one_or_none()
    who = (requester.full_name or requester.email.split("@")[0]) if requester else "Someone"
    parts = [f"{who}, {role.value.replace('_', ' ').title()}" if role else who]
    if approval.action_type in (A.PLACE_BID, A.CREATE_OFFER, A.EXERCISE_OPTION):
        finance = (await db.execute(select(ClubFinance).where(ClubFinance.club_id == club.id))).scalar_one_or_none()
        if finance is not None:
            parts.append(f"budget after {money(max(Decimal(0), finance.transfer_remaining - Decimal(approval.amount)))}")
    return {
        "title": title, "body": " · ".join(parts), "group_key": f"approval:{approval.id}",
        "deadline_at": approval.expires_at,
        "actions": [{"action": "open", "title": "Review", "url": f"/club/approvals?id={approval.id}"}],
    }

