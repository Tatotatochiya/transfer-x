"""Move reminders (docs/feature_spec/move-reminders).

Who holds the move on an open offer, deal or enquiry, whether the viewer may
remind them, and sending the reminder: in-app, email and push through the
notification pipeline, an audit event, and a row in `move_reminders` that the
cooldown and escalation rules count. A reminder never changes the transaction.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.reminders.models import MoveReminder

# §1 D4–D6.
SHOW_AFTER = timedelta(hours=24)
COOLDOWN = timedelta(hours=48)
DEADLINE_SHOW_AFTER = timedelta(hours=2)
DEADLINE_COOLDOWN = timedelta(hours=12)
DEADLINE_WINDOW = timedelta(hours=72)
# In a demo (app/demo) nothing waits a day: a reminder makes the house answer now.
DEMO_SHOW_AFTER = timedelta(0)
DEMO_COOLDOWN = timedelta(minutes=1)
ESCALATE_AFTER = timedelta(days=7)
ESCALATE_AFTER_IGNORED = 2
AUTO_FIRST = timedelta(days=3)
AUTO_SECOND = timedelta(days=7)
# Older than this, a transaction has been abandoned rather than stalled:
# no automatic reminders, so switching the job on doesn't chase dead deals.
AUTO_MAX_IDLE = timedelta(days=30)
NOTE_MAX = 200

SUBJECTS = ("offer", "deal", "enquiry")
_AUDIT_ENTITY = {"deal": "DEAL", "offer": "offer", "enquiry": "enquiry"}


class ReminderError(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


@dataclass
class Holder:
    """Someone whose move it is."""
    kind: str                 # "club", "agent" or "player"
    id: uuid.UUID             # club id, agent profile id or player id
    name: str                 # as the waiting side may see it (masked if need be)
    move_key: str             # e.g. "deal:AGENT_NEGOTIATION:propose-commission"
    what: str                 # "your commission proposal", worded to the holder
    user_ids: list[uuid.UUID] = field(default_factory=list)


@dataclass
class Viewer:
    user_id: uuid.UUID
    club_id: uuid.UUID | None = None
    agent_id: uuid.UUID | None = None
    can_act: bool = True      # their role may trade (MARKET_WRITE / DEAL_WRITE)
    name: str | None = None   # an agent's display name


@dataclass
class Subject:
    type: str
    obj: object
    player_name: str
    amount: str | None
    idle_since: datetime
    party_clubs: list[uuid.UUID]
    agent_ids: list[uuid.UUID]
    country: str | None
    link: str


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def money(v) -> str:
    """The app's compact format: "£34.5M", "£450K" (TOKENS.md "Money")."""
    n = float(v)
    one = lambda x: f"{x:.1f}".removesuffix(".0")  # noqa: E731
    if n >= 1e9:
        return f"£{one(n / 1e9)}B"
    if n >= 1e6:
        return f"£{one(n / 1e6)}M"
    if n >= 1e3:
        return f"£{round(n / 1e3)}K"
    return f"£{round(n)}"


# ── Loading a subject ─────────────────────────────────────────────────────────

async def load_subject(db: AsyncSession, subject_type: str, subject_id: uuid.UUID) -> Subject | None:
    if subject_type == "offer":
        from sqlalchemy.orm import selectinload

        from app.offers.models import Offer, OfferEvent, OfferEventType

        o = (await db.execute(
            select(Offer).where(Offer.id == subject_id)
            .options(selectinload(Offer.player), selectinload(Offer.from_club), selectinload(Offer.to_club))
        )).scalar_one_or_none()
        if o is None:
            return None
        moved = (await db.execute(
            select(func.max(OfferEvent.created_at)).where(
                OfferEvent.offer_id == o.id,
                OfferEvent.event_type.in_([OfferEventType.SENT, OfferEventType.COUNTERED, OfferEventType.IMPROVED]),
            )
        )).scalar()
        fee = o.loan_fee if getattr(o, "loan_fee", None) else o.fee_amount
        return Subject(
            "offer", o, o.player.name if o.player else "the player",
            money(fee) if fee else None, _aware(moved or o.created_at),
            [c for c in (o.from_club_id, o.to_club_id) if c], [],
            (o.from_club.country if o.from_club else None), f"/offers/{o.id}",
        )
    if subject_type == "deal":
        from sqlalchemy.orm import selectinload

        from app.deals.models import Deal

        d = (await db.execute(
            select(Deal).where(Deal.id == subject_id)
            .options(selectinload(Deal.player), selectinload(Deal.buyer_club), selectinload(Deal.seller_club),
                     selectinload(Deal.personal_terms), selectinload(Deal.medical_check))
        )).scalar_one_or_none()
        if d is None:
            return None
        from app.deals import service as deals_service

        neg = await deals_service.get_agent_negotiation(db, d.id)
        agents = {a for a in (d.commission_agent_id, neg.agent_id if neg else None,
                              d.personal_terms.agent_id if d.personal_terms else None) if a}
        fee = d.agreed_fee if d.agreed_fee and Decimal(d.agreed_fee) > 0 else getattr(d, "loan_fee", None)
        return Subject(
            "deal", d, d.player.name if d.player else "the player",
            money(fee) if fee else None, _aware(d.updated_at),
            [c for c in (d.buyer_club_id, d.seller_club_id) if c], list(agents),
            (d.buyer_club.country if d.buyer_club else None), f"/deals/{d.id}",
        )
    if subject_type == "enquiry":
        from sqlalchemy.orm import selectinload

        from app.enquiries.models import Enquiry

        e = (await db.execute(
            select(Enquiry).where(Enquiry.id == subject_id)
            .options(selectinload(Enquiry.player), selectinload(Enquiry.from_club), selectinload(Enquiry.to_club))
        )).scalar_one_or_none()
        if e is None:
            return None
        return Subject(
            "enquiry", e, e.player.name if e.player else "the player", None,
            _aware(e.updated_at or e.created_at), [e.from_club_id, e.to_club_id], [],
            (e.from_club.country if e.from_club else None), f"/enquiries/{e.id}",
        )
    return None


# ── Who holds the move ────────────────────────────────────────────────────────

async def _club_holder(db, club, move_key: str, what: str, *, shown_as: str | None = None) -> Holder:
    from app.notifications.models import NotificationType
    from app.notifications.service import club_recipient_user_ids

    users = await club_recipient_user_ids(db, club.id, NotificationType.MOVE_REMINDER)
    return Holder("club", club.id, shown_as or club.name, move_key, what, users)


async def _agent_holder(db, agent_id: uuid.UUID, move_key: str, what: str) -> Holder | None:
    from app.auth.models import AgentProfile

    a = (await db.execute(select(AgentProfile).where(AgentProfile.id == agent_id))).scalar_one_or_none()
    if a is None:
        return None
    return Holder("agent", a.id, a.display_name, move_key, what, [a.user_id])


async def player_user_id(db, player_id: uuid.UUID) -> uuid.UUID | None:
    from app.auth.models import PlayerProfile

    return (await db.execute(select(PlayerProfile.user_id).where(PlayerProfile.player_id == player_id))).scalar()


async def holders(db: AsyncSession, s: Subject) -> list[Holder]:
    """Everyone currently holding a move on `s` (usually one). Mirrors the
    status cards (dealStatus.ts, offerStatus.ts) but is the authority."""
    if s.type == "offer":
        from app.common.masking import buyer_name
        from app.offers.models import OfferStatus

        o = s.obj
        if o.status not in (OfferStatus.SENT, OfferStatus.COUNTERED) or o.to_club is None:
            return []
        # The club that didn't act last answers. The seller sees an anonymous
        # buyer masked, so the buyer is named to the seller as it's shown.
        if o.last_actor_club_id == o.to_club_id:
            return [await _club_holder(db, o.from_club, "offer:answer", f"an answer to the counter for {s.player_name}",
                                       shown_as=buyer_name(o, o.from_club, o.to_club_id))]
        return [await _club_holder(db, o.to_club, "offer:answer", f"an answer to the offer for {s.player_name}")]

    if s.type == "enquiry":
        from app.common.masking import buyer_name
        from app.enquiries.models import EnquiryStatus

        e = s.obj
        if e.status != EnquiryStatus.OPEN:
            return []
        if e.last_actor_club_id == e.to_club_id:
            return [await _club_holder(db, e.from_club, "enquiry:reply", f"a reply about {s.player_name}",
                                       shown_as=buyer_name(e, e.from_club, e.to_club_id))]
        return [await _club_holder(db, e.to_club, "enquiry:reply", f"a reply to the enquiry about {s.player_name}")]

    from app.agents.models import AgreementStatus
    from app.deals import service as deals_service
    from app.deals.models import DealStage, DealStatus

    d = s.obj
    if d.status not in (DealStatus.IN_PROGRESS, DealStatus.PENDING_COMPLETION):
        return []
    P = s.player_name
    buyer, seller = d.buyer_club, d.seller_club

    if d.stage == DealStage.AGREEMENT:
        out = [await _club_holder(db, buyer, "deal:AGREEMENT:advance", f"moving {P}'s deal on to personal terms")]
        if seller is not None:
            out.append(await _club_holder(db, seller, "deal:AGREEMENT:advance", f"moving {P}'s deal on to personal terms"))
        return out

    if d.stage == DealStage.AGENT_NEGOTIATION:
        neg = await deals_service.get_agent_negotiation(db, d.id)
        agent_id = neg.agent_id if neg else d.commission_agent_id
        proposed = neg is not None and (neg.commission_pct is not None or neg.commission_amount is not None)
        if agent_id and (not proposed or neg.club_agreement == AgreementStatus.DECLINED):
            again = proposed and neg.club_agreement == AgreementStatus.DECLINED
            h = await _agent_holder(db, agent_id, "deal:AGENT_NEGOTIATION:propose-commission",
                                    f"{'a new' if again else 'your'} commission proposal for {P}")
            return [h] if h else []
        if proposed and neg.club_agreement == AgreementStatus.PENDING:
            return [await _club_holder(db, buyer, "deal:AGENT_NEGOTIATION:answer-commission",
                                       f"an answer to the commission proposal for {P}")]
        if proposed and neg.club_agreement == AgreementStatus.AGREED:
            return [await _club_holder(db, buyer, "deal:AGENT_NEGOTIATION:advance", f"moving {P}'s deal on to personal terms")]
        return []

    if d.stage == DealStage.PERSONAL_TERMS:
        terms = d.personal_terms
        if terms is None:
            if d.commission_agent_id:
                h = await _agent_holder(db, d.commission_agent_id, "deal:PERSONAL_TERMS:propose", f"personal terms for {P}")
                return [h] if h else []
            return [await _club_holder(db, buyer, "deal:PERSONAL_TERMS:propose", f"personal terms for {P}")]
        if terms.player_consent == AgreementStatus.AGREED:
            out = [await _club_holder(db, buyer, "deal:PERSONAL_TERMS:advance", f"moving {P}'s deal on to paperwork")]
            if seller is not None:
                out.append(await _club_holder(db, seller, "deal:PERSONAL_TERMS:advance", f"moving {P}'s deal on to paperwork"))
            return out
        if terms.player_consent == AgreementStatus.PENDING:
            if terms.agent_id:
                h = await _agent_holder(db, terms.agent_id, "deal:PERSONAL_TERMS:answer", f"an answer to {P}'s personal terms")
                return [h] if h else []
            uid = await player_user_id(db, d.player_id)
            if uid:
                return [Holder("player", d.player_id, P, "deal:PERSONAL_TERMS:answer", "your answer to the personal terms", [uid])]
            return [await _club_holder(db, buyer, "deal:PERSONAL_TERMS:record", f"recording {P}'s answer to the terms")]
        return []

    if d.stage == DealStage.PAPERWORK:
        out = []
        for club in (buyer, seller):
            if club is not None and deals_service.outstanding_paperwork_for(d, club.id):
                out.append(await _club_holder(db, club, "deal:PAPERWORK:steps", f"its paperwork for {P}'s transfer"))
        return out

    # CONFIRMED: completion has its own deadline and escalation (check_deal_sla_breaches).
    return []


# ── The viewer's state ────────────────────────────────────────────────────────

def _is_party(s: Subject, v: Viewer) -> bool:
    return (v.club_id is not None and v.club_id in s.party_clubs) or (
        s.type == "deal" and v.agent_id is not None and v.agent_id in s.agent_ids
    )


def _is_holder(h: Holder, v: Viewer) -> bool:
    return (h.kind == "club" and h.id == v.club_id) or (h.kind == "agent" and h.id == v.agent_id)


async def _deadline_soon(db: AsyncSession, s: Subject, now: datetime) -> bool:
    from app.transfer_window import service as tw

    w = await tw.get_current_window(db, s.country, now)
    return w is not None and _aware(w.closes_at) - now <= DEADLINE_WINDOW


async def _reminders_since(db, s: Subject, since: datetime) -> list[MoveReminder]:
    rows = (await db.execute(
        select(MoveReminder).where(
            MoveReminder.subject_type == s.type, MoveReminder.subject_id == s.obj.id,
            MoveReminder.created_at >= since,
        ).order_by(MoveReminder.created_at)
    )).scalars().all()
    return list(rows)


def _same_side(r: MoveReminder, v: Viewer) -> bool:
    if r.automatic:
        return False
    if v.club_id is not None:
        return r.sender_club_id == v.club_id
    return r.sender_user_id == v.user_id


@dataclass
class State:
    holder: Holder | None
    waiting_since: datetime | None
    can_send: bool
    reason: str | None
    next_allowed_at: datetime | None
    would_escalate: bool
    last: MoveReminder | None
    preview: str | None
    # The latest reminder sent to the viewer since the move last moved.
    to_you: MoveReminder | None = None


async def _in_demo(db: AsyncSession, s: Subject) -> bool:
    from app.demo.service import open_demo_rows

    table = {"offer": "offers", "deal": "deals", "enquiry": "enquiries"}[s.type]
    return s.obj.id in await open_demo_rows(db, table)


async def state_for(db: AsyncSession, s: Subject, v: Viewer, now: datetime | None = None) -> State:
    now = now or datetime.now(timezone.utc)
    all_holders = await holders(db, s)
    mine = any(_is_holder(h, v) for h in all_holders)
    others = [h for h in all_holders if not _is_holder(h, v)]
    holder = others[0] if others else None
    since = s.idle_since
    reminders = await _reminders_since(db, s, since) if since else []
    last = reminders[-1] if reminders else None

    to_you = next((r for r in reversed(reminders)
                   if (r.holder_kind == "club" and r.holder_id == v.club_id)
                   or (r.holder_kind == "agent" and r.holder_id == v.agent_id)), None)

    def out(can, reason=None, nxt=None, esc=False):
        preview = message_for(s, holder, sender_label(s, v, holder), now, esc) if holder else None
        return State(holder, since if holder else None, can, reason, nxt, esc, last, preview, to_you)

    if mine:
        return out(False, "It's your move.")
    if holder is None:
        return out(False, "Nobody else is holding this up.")
    if not v.can_act:
        return out(False, "Your role can't act on this transfer.")
    if await _in_demo(db, s):
        show_after, cooldown = DEMO_SHOW_AFTER, DEMO_COOLDOWN
    elif await _deadline_soon(db, s, now):
        show_after, cooldown = DEADLINE_SHOW_AFTER, DEADLINE_COOLDOWN
    else:
        show_after, cooldown = SHOW_AFTER, COOLDOWN
    if now - since < show_after:
        return out(False, f"You can send a reminder from {_when(since + show_after, now)}.", since + show_after)
    mine_sent = [r for r in reminders if _same_side(r, v)]
    if mine_sent:
        nxt = _aware(mine_sent[-1].created_at) + cooldown
        if now < nxt:
            return out(False, f"You reminded them {_ago(_aware(mine_sent[-1].created_at), now)}. "
                              f"You can send another from {_when(nxt, now)}.", nxt)
    esc = len(reminders) >= ESCALATE_AFTER_IGNORED or now - since >= ESCALATE_AFTER
    return out(True, None, None, esc)


def _ago(t: datetime, now: datetime) -> str:
    h = int((now - t).total_seconds() // 3600)
    if h < 1:
        return "just now"
    if h < 24:
        return f"{h} hour{'s' if h != 1 else ''} ago"
    d = h // 24
    return "yesterday" if d == 1 else f"{d} days ago"


def _when(t: datetime, now: datetime) -> str:
    """UK time, as the rest of TransferX's deadlines are."""
    from zoneinfo import ZoneInfo

    uk = ZoneInfo("Europe/London")
    t, now = t.astimezone(uk), now.astimezone(uk)
    if t.date() == now.date():
        return t.strftime("%H:%M")
    return t.strftime("%-d %b, %H:%M")


# ── Wording ───────────────────────────────────────────────────────────────────

def sender_label(s: Subject, v: Viewer | None, holder: Holder | None) -> str:
    """How the holder may see the sender: masked for an anonymous buyer."""
    if v is None:
        return waiting_label(s, holder)
    if v.club_id is None:
        return v.name or "The agent"
    from app.common.masking import buyer_name

    if s.type in ("offer", "enquiry") and v.club_id == s.obj.from_club_id and holder is not None:
        return buyer_name(s.obj, s.obj.from_club, holder.id if holder.kind == "club" else None)
    from app.clubs.models import Club

    for club in (getattr(s.obj, "from_club", None), getattr(s.obj, "to_club", None),
                 getattr(s.obj, "buyer_club", None), getattr(s.obj, "seller_club", None)):
        if isinstance(club, Club) and club.id == v.club_id:
            return club.name
    return "The other club"


def waiting_label(s: Subject, holder: Holder | None) -> str:
    """Who is waiting, for an automatic reminder: the party that isn't the
    holder, masked as the holder may see it."""
    from app.common.masking import buyer_name

    o = s.obj
    if s.type in ("offer", "enquiry"):
        if holder is not None and holder.kind == "club" and holder.id == o.to_club_id:
            return buyer_name(o, o.from_club, o.to_club_id)
        return o.to_club.name if o.to_club else "The other club"
    buyer, seller = o.buyer_club, o.seller_club
    if holder is not None and holder.kind == "club":
        other = seller if buyer is not None and holder.id == buyer.id else buyer
        return other.name if other is not None else "The other club"
    return buyer.name if buyer is not None else "The buying club"


def message_for(s: Subject, holder: Holder, sender: str, now: datetime, escalated: bool) -> str:
    days = max(1, int((now - s.idle_since).total_seconds() // 86400))
    money_part = f" ({s.amount})" if s.amount else ""
    head = f"{sender} is waiting for {holder.what}{money_part}"
    if holder.what.startswith(("moving", "its paperwork", "recording")):
        head = f"{sender} is waiting on {holder.what}{money_part}"
    return f"{head} · {days} day{'s' if days != 1 else ''}"


# ── Sending ───────────────────────────────────────────────────────────────────

async def send(
    db: AsyncSession, s: Subject, v: Viewer | None, *, note: str | None = None,
    now: datetime | None = None, holder: Holder | None = None,
) -> MoveReminder:
    """Send a reminder from `v` (or TransferX when `v` is None) to the holder.
    The caller has checked `state_for`; this re-checks nothing and commits nothing."""
    from app.audit import service as audit_service

    now = now or datetime.now(timezone.utc)
    if v is not None:
        st = await state_for(db, s, v, now)
        if not st.can_send:
            raise ReminderError(409, st.reason or "You can't send a reminder now.")
        holder, escalated = st.holder, st.would_escalate
    else:
        reminders = await _reminders_since(db, s, s.idle_since)
        escalated = len(reminders) >= ESCALATE_AFTER_IGNORED or now - s.idle_since >= ESCALATE_AFTER
    assert holder is not None
    note = (note or "").strip()[:NOTE_MAX] or None

    r = MoveReminder(
        subject_type=s.type, subject_id=s.obj.id, move_key=holder.move_key,
        holder_kind=holder.kind, holder_id=holder.id,
        sender_user_id=v.user_id if v else None, sender_club_id=v.club_id if v else None,
        escalated=escalated, automatic=v is None, note=note, created_at=now,
    )
    db.add(r)
    await db.flush()

    sender = sender_label(s, v, holder)
    text = message_for(s, holder, sender, now, escalated)
    await _notify(db, s, holder, v, text, note, escalated, now)

    actor = "TransferX" if v is None else sender
    verb = "escalated it to" if escalated else "sent a reminder to"
    await audit_service.emit(
        db, entity_type=_AUDIT_ENTITY[s.type], entity_id=s.obj.id,
        action="MOVE_ESCALATED" if escalated else "MOVE_REMINDER",
        actor_user_id=v.user_id if v else None,
        payload={"holder": holder.kind, "move": holder.move_key, "automatic": v is None, "note": note},
        description=f"{actor} {verb} {holder.name}" + (f": “{note}”" if note else ""),
    )
    return r


async def _notify(db, s: Subject, holder: Holder, v: Viewer | None, text: str, note: str | None,
                  escalated: bool, now: datetime) -> None:
    from app.notifications.models import NotificationType
    from app.notifications.service import create_notification, club_recipient_user_ids

    type_ = NotificationType.MOVE_ESCALATED if escalated else NotificationType.MOVE_REMINDER
    reminders = await _reminders_since(db, s, s.idle_since)
    why = None
    if escalated:
        n = len(reminders)
        why = (f"This is reminder number {n}." if n >= ESCALATE_AFTER_IGNORED + 1
               else f"It has been waiting {int((now - s.idle_since).days)} days.")
    body = " ".join(x for x in (f"“{note}”" if note else None, why) if x) or None
    title = "Still waiting on you" if escalated else "A transfer is waiting on you"
    player_id = getattr(s.obj, "player_id", None)

    told: set[uuid.UUID] = set()
    for uid in holder.user_ids:
        if uid in told:
            continue
        told.add(uid)
        await create_notification(
            db, recipient_user_id=uid, type=type_, message=text, link=s.link,
            related_player_id=player_id, title=title, body=body,
            group_key=f"remind:{s.type}:{s.obj.id}",
        )
    if not escalated:
        return

    # §1 D5: an escalation also tells whoever can unblock it.
    fyi = f"{s.player_name}'s transfer is waiting on {holder.name}: {holder.what.replace('your ', 'their ')}."
    extra: list[uuid.UUID] = []
    sender_club = v.club_id if v else None
    if holder.kind == "agent":
        uid = await player_user_id(db, player_id) if player_id else None
        if uid:
            extra.append(uid)
        for club_id in s.party_clubs:
            if club_id != sender_club:
                extra += await club_recipient_user_ids(db, club_id, NotificationType.MOVE_STALLED)
    elif holder.kind == "player":
        if s.agent_ids:
            from app.auth.models import AgentProfile

            uid = (await db.execute(select(AgentProfile.user_id).where(AgentProfile.id == s.agent_ids[0]))).scalar()
            if uid:
                extra.append(uid)
        elif getattr(s.obj, "seller_club_id", None):
            extra += await club_recipient_user_ids(db, s.obj.seller_club_id, NotificationType.MOVE_STALLED)
    for uid in extra:
        if uid in told:
            continue
        told.add(uid)
        await create_notification(
            db, recipient_user_id=uid, type=NotificationType.MOVE_STALLED, message=fyi, link=s.link,
            related_player_id=player_id, title="A transfer is stuck", body=why,
            group_key=f"remind:{s.type}:{s.obj.id}",
        )


# ── Automatic reminders (§1 D6) ───────────────────────────────────────────────

async def send_automatic(db: AsyncSession, now: datetime | None = None) -> int:
    """At 3 and 7 days without movement, remind whoever holds the move, once
    each per move. Returns how many reminders went out. Commits nothing."""
    from app.deals.models import Deal, DealStatus
    from app.enquiries.models import Enquiry, EnquiryStatus
    from app.offers.models import Offer, OfferStatus

    now = now or datetime.now(timezone.utc)
    ids: list[tuple[str, uuid.UUID]] = []
    ids += [("offer", i) for i in (await db.execute(
        select(Offer.id).where(Offer.status.in_([OfferStatus.SENT, OfferStatus.COUNTERED])))).scalars()]
    ids += [("deal", i) for i in (await db.execute(
        select(Deal.id).where(Deal.status == DealStatus.IN_PROGRESS))).scalars()]
    ids += [("enquiry", i) for i in (await db.execute(
        select(Enquiry.id).where(Enquiry.status == EnquiryStatus.OPEN))).scalars()]

    # Demo transactions (app/demo): the house answers them itself, and a
    # reminder about one would outlive the demo's reset.
    from app.demo.service import open_demo_rows

    in_demo = {("offer", i) for i in await open_demo_rows(db, "offers")}
    in_demo |= {("deal", i) for i in await open_demo_rows(db, "deals")}
    in_demo |= {("enquiry", i) for i in await open_demo_rows(db, "enquiries")}
    ids = [k for k in ids if k not in in_demo]

    sent = 0
    for kind, sid in ids:
        s = await load_subject(db, kind, sid)
        if s is None or s.idle_since is None:
            continue
        idle = now - s.idle_since
        if idle < AUTO_FIRST or idle > AUTO_MAX_IDLE:
            continue
        earlier = [r for r in await _reminders_since(db, s, s.idle_since) if r.automatic]
        for h in await holders(db, s):
            autos = [r for r in earlier if r.holder_id == h.id]
            if (not autos and idle >= AUTO_FIRST) or (len(autos) == 1 and idle >= AUTO_SECOND):
                await send(db, s, None, now=now, holder=h)
                sent += 1
    return sent
