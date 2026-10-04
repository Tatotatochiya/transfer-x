"""One conversation per transfer (Phase 3, product ADR 0008).

A transfer is a player moving from one club to another: the enquiry, the
offers and the deal between the same two clubs about the same player. Each
of those kept its own messages, with its own visibility rules:

- enquiry and offer messages: between the two clubs;
- deal-room comments: everyone on the deal (both clubs, the agent, the
  player), or one club only;
- the agent negotiation's club thread: both clubs and the agent.

This module reads all of them as one conversation, in order, filtered by
those same rules and with an anonymous buyer masked the same way. Posting
goes through each system's own function, so its notifications, audit and
permission checks are unchanged. The storage stays where it is until the
old pages are retired (ADR 0008, decision 4).
"""
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.models import User
from app.common.masking import buyer_is_masked, masked_name
from app.deals.models import Deal, DealStatus
from app.enquiries.models import Enquiry, EnquiryStatus
from app.offers.models import Offer, OfferMessage, OfferStatus

# Who can read a message, in the words the app shows.
AUDIENCE_LABEL = {
    "both_clubs": "Both clubs",
    "deal_everyone": "Both clubs, the agent and the player",
    "our_club": "Only your club",
    "with_agent": "Both clubs and the agent",
}


class ConversationError(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


@dataclass
class Transfer:
    player_id: uuid.UUID
    buyer_club_id: uuid.UUID
    seller_club_id: uuid.UUID | None
    viewer_club_id: uuid.UUID
    enquiries: list = field(default_factory=list)
    offers: list = field(default_factory=list)
    deals: list = field(default_factory=list)

    @property
    def viewer_is_buyer(self) -> bool:
        return str(self.viewer_club_id) == str(self.buyer_club_id)

    @property
    def live_deal(self):
        live = [d for d in self.deals if d.status != DealStatus.COLLAPSED]
        return live[-1] if live else None

    @property
    def open_offer(self):
        live = [o for o in self.offers if o.status in (OfferStatus.SENT, OfferStatus.COUNTERED)]
        return live[-1] if live else None

    @property
    def open_enquiry(self):
        live = [e for e in self.enquiries if e.status == EnquiryStatus.OPEN]
        return live[-1] if live else None


def _aware(dt: datetime | None) -> datetime:
    if dt is None:
        return datetime.min.replace(tzinfo=timezone.utc)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


async def resolve(
    db: AsyncSession, viewer_club_id: uuid.UUID, *,
    offer_id: uuid.UUID | None = None, deal_id: uuid.UUID | None = None, enquiry_id: uuid.UUID | None = None,
) -> Transfer:
    """The transfer around one enquiry, offer or deal, for one of its two clubs."""
    if deal_id:
        anchor = await db.get(Deal, deal_id)
        key = anchor and (anchor.player_id, anchor.buyer_club_id, anchor.seller_club_id)
    elif offer_id:
        anchor = await db.get(Offer, offer_id)
        key = anchor and (anchor.player_id, anchor.from_club_id, anchor.to_club_id)
    elif enquiry_id:
        anchor = await db.get(Enquiry, enquiry_id)
        key = anchor and (anchor.player_id, anchor.from_club_id, anchor.to_club_id)
    else:
        raise ConversationError(422, "Say which enquiry, offer or deal")
    if not key:
        raise ConversationError(404, "Not found")
    player_id, buyer, seller = key
    if str(viewer_club_id) not in {str(buyer), str(seller)}:
        raise ConversationError(403, "Not a party to this transfer")

    def same(col_player, col_buyer, col_seller):
        conds = [col_player == player_id, col_buyer == buyer]
        conds.append(col_seller == seller if seller is not None else col_seller.is_(None))
        return conds

    # Fresh rows every time: after a post, this session may still hold the
    # offer or enquiry with its messages as they were before it.
    t = Transfer(player_id=player_id, buyer_club_id=buyer, seller_club_id=seller, viewer_club_id=viewer_club_id)
    t.enquiries = list((await db.execute(
        select(Enquiry).where(*same(Enquiry.player_id, Enquiry.from_club_id, Enquiry.to_club_id))
        .options(selectinload(Enquiry.messages), selectinload(Enquiry.from_club), selectinload(Enquiry.to_club))
        .order_by(Enquiry.created_at)
        .execution_options(populate_existing=True)
    )).scalars())
    t.offers = list((await db.execute(
        select(Offer).where(*same(Offer.player_id, Offer.from_club_id, Offer.to_club_id), Offer.status != OfferStatus.DRAFT)
        .options(selectinload(Offer.messages).selectinload(OfferMessage.sender_club),
                 selectinload(Offer.from_club), selectinload(Offer.to_club))
        .order_by(Offer.created_at)
        .execution_options(populate_existing=True)
    )).scalars())
    t.deals = list((await db.execute(
        select(Deal).where(*same(Deal.player_id, Deal.buyer_club_id, Deal.seller_club_id))
        .options(selectinload(Deal.buyer_club), selectinload(Deal.seller_club))
        .order_by(Deal.created_at)
        .execution_options(populate_existing=True)
    )).scalars())
    return t


async def _negotiation_for(db: AsyncSession, deal):
    from app.agents.models import AgentNegotiation

    return (await db.execute(
        select(AgentNegotiation).where(AgentNegotiation.deal_id == deal.id)
        .order_by(AgentNegotiation.created_at.desc()).limit(1)
    )).scalar_one_or_none()


async def messages(db: AsyncSession, t: Transfer, viewer: User) -> list[dict]:
    from app.agents.models import NegotiationMessage, NegotiationThread
    from app.deals import room_service
    from app.deals.room_models import CommentAudience, DealComment

    out: list[dict] = []
    me = str(t.viewer_club_id)

    for e in t.enquiries:
        for m in e.messages or []:
            mine = str(m.sender_club_id) == me
            if mine:
                who = "You"
            elif str(m.sender_club_id) == str(e.from_club_id) and e.is_anonymous:
                who = masked_name(e.from_club)
            else:
                club = e.from_club if str(m.sender_club_id) == str(e.from_club_id) else e.to_club
                who = club.name if club else "The other club"
            out.append(dict(id=m.id, source="enquiry", audience="both_clubs", author=who, mine=mine,
                            body=m.body, created_at=m.created_at, context="Enquiry"))

    for o in t.offers:
        context = "Offer"
        for m in o.messages or []:
            mine = str(m.sender_club_id) == me
            if mine:
                who = "You"
            elif str(m.sender_club_id) == str(o.from_club_id) and buyer_is_masked(o, t.viewer_club_id):
                who = masked_name(o.from_club)
            else:
                who = m.sender_club.name if m.sender_club else "The other club"
            out.append(dict(id=m.id, source="offer", audience="both_clubs", author=who, mine=mine,
                            body=m.body, created_at=m.created_at, context=context))

    viewer_members = None
    for d in t.deals:
        visible = room_service.visible_audiences(d, t.viewer_club_id, False)
        comments = (await db.execute(
            select(DealComment).where(DealComment.deal_id == d.id, DealComment.audience.in_(visible))
            .options(selectinload(DealComment.author)).order_by(DealComment.created_at)
        )).scalars().all()
        if comments and viewer_members is None:
            from app.notifications import service as notif_service

            viewer_members = {str(u) for u in await notif_service.club_member_user_ids(db, t.viewer_club_id)}
        for c in comments:
            mine = c.author_user_id is not None and str(c.author_user_id) == str(viewer.id)
            if mine:
                who = "You"
            elif c.author is not None and str(c.author_user_id) in (viewer_members or set()):
                # A colleague: by name, which only their own club sees.
                who = c.author.display_label
            else:
                who = await room_service.label_for_user(db, c.author_user_id) or "Someone"
            out.append(dict(
                id=c.id, source="deal", mine=mine, author=who, body=c.body, created_at=c.created_at, context="Deal",
                audience="deal_everyone" if c.audience == CommentAudience.SHARED else "our_club",
            ))
        neg = await _negotiation_for(db, d)
        if neg is not None:
            from app.agents.negotiation_messages import sender_label

            msgs = (await db.execute(
                select(NegotiationMessage).where(NegotiationMessage.negotiation_id == neg.id,
                                                 NegotiationMessage.thread == NegotiationThread.CLUB_SIDE)
                .options(selectinload(NegotiationMessage.sender)).order_by(NegotiationMessage.created_at)
            )).scalars().all()
            for m in msgs:
                mine = m.sender_user_id is not None and str(m.sender_user_id) == str(viewer.id)
                who = "You" if mine else (await sender_label(db, m.sender) if m.sender else "Someone").replace(" — ", ": ")
                out.append(dict(id=m.id, source="agent", audience="with_agent", author=who, mine=mine,
                                body=m.body, created_at=m.created_at, context="Agent negotiation"))

    out.sort(key=lambda m: _aware(m["created_at"]))
    for m in out:
        m["audience_label"] = AUDIENCE_LABEL[m["audience"]]
    return out


async def post_options(db: AsyncSession, t: Transfer) -> list[str]:
    """Who the viewer can write to now, most open first. Empty once nothing
    is live (every enquiry closed, no open offer, no live deal)."""
    deal = t.live_deal
    if deal is not None:
        opts = ["deal_everyone", "our_club"]
        if await _negotiation_for(db, deal) is not None:
            opts.append("with_agent")
        return opts
    if t.open_offer is not None or t.open_enquiry is not None:
        return ["both_clubs"]
    return []


async def post(db: AsyncSession, t: Transfer, user: User, club, *, audience: str, body: str,
               mentioned_user_ids: list | None = None) -> None:
    """Write through the system that owns this audience right now."""
    from app.clubs.capabilities import Capability, ensure_club_capability

    body = body.strip()
    if not body:
        raise ConversationError(422, "Write a message first")
    if audience not in await post_options(db, t):
        raise ConversationError(409, "You can't write to that audience on this transfer now")

    if audience == "both_clubs":
        await ensure_club_capability(db, user, Capability.MARKET_WRITE)
        offer = t.open_offer
        if offer is not None:
            from app.offers import actions

            try:
                await actions.add_message(db, user, club, offer, body)
            except actions.OfferActionError as exc:
                raise ConversationError(exc.status_code, str(exc.detail))
            return
        from app.enquiries import service as enquiries_service

        enquiry = await enquiries_service.get_enquiry(db, t.open_enquiry.id)
        try:
            await enquiries_service.add_message(db, enquiry, sender_club_id=club.id, body=body, actor_user_id=user.id)
            await db.commit()
        except ValueError as exc:
            await db.rollback()
            raise ConversationError(400, str(exc))
        return

    await ensure_club_capability(db, user, Capability.DEAL_WRITE)
    deal = t.live_deal
    if audience in ("deal_everyone", "our_club"):
        from app.deals import room_service
        from app.deals.room_models import CommentAudience

        private = CommentAudience.BUYER_ONLY if t.viewer_is_buyer else CommentAudience.SELLER_ONLY
        # Mentions only where everyone mentioned can read the message.
        mentioned = []
        if audience == "deal_everyone" and mentioned_user_ids:
            allowed = {str(p["user_id"]) for p in await room_service.get_deal_participants(db, deal)}
            mentioned = [m for m in mentioned_user_ids if str(m) in allowed]
        await room_service.create_comment(
            db, deal.id, author_user_id=user.id, body=body, parent_id=None, mentioned_user_ids=mentioned,
            audience=CommentAudience.SHARED if audience == "deal_everyone" else private,
        )
        await room_service.notify_comment(db, deal, user, set(mentioned), body)
        await db.commit()
        return

    # with_agent: the negotiation's club thread, which the agent is told about.
    from app.agents import negotiation_messages
    from app.agents.models import NegotiationThread

    neg = await _negotiation_for(db, deal)
    await negotiation_messages.create_message(
        db, negotiation_id=neg.id, thread=NegotiationThread.CLUB_SIDE, sender_user_id=user.id, body=body,
    )
    await negotiation_messages.notify_counterparty(
        db, negotiation=neg, deal=deal, thread=NegotiationThread.CLUB_SIDE, sender=user, text=body,
    )
    await db.commit()
