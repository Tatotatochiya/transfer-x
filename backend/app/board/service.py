"""The Transfers board (Phase 3, product ADR 0008): every player a club is
buying or selling, once, at its furthest point.

Built from each module's own reads (offers, deals, enquiries, sales), like
the dashboard. A player can have an enquiry, two offers and a deal at once;
the board shows the furthest of them, and counts the others in the same
column. Ended items (collapsed deals, offers that went nowhere, ended
listings) go in a Closed drawer for a while, unless the player is active
again on the same side.
"""
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.board.schemas import BoardCard, BoardColumn, BoardResponse
from app.common.masking import buyer_name
from app.common.schemas import WhoseMove
from app.deals import service as deals_service
from app.deals.models import DealStage, DealStatus
from app.offers import service as offers_service
from app.offers.models import OfferStatus
from app.sales import service as sales_service
from app.sales.models import Bid, BidStatus, Sale, SaleStatus, SaleType

COLUMNS = [
    ("talking", "Talking"),
    ("offers", "Offers"),
    ("fee_agreed", "Fee agreed"),
    ("terms", "Personal terms"),
    ("paperwork", "Paperwork"),
    ("done", "Done"),
]
RANK = {key: i for i, (key, _) in enumerate(COLUMNS)}
DEAL_COLUMN = {
    DealStage.AGREEMENT: "fee_agreed",
    DealStage.AGENT_NEGOTIATION: "terms",
    DealStage.PERSONAL_TERMS: "terms",
    DealStage.PAPERWORK: "paperwork",
    DealStage.CONFIRMED: "paperwork",
    DealStage.COMPLETED: "done",
}
DONE_FOR = timedelta(days=120)    # completed transfers stay in Done this long
CLOSED_FOR = timedelta(days=60)   # and ended items in the Closed drawer
_PAGE = 1000
_PAPERWORK = {
    "agreement_buyer": "sign the transfer agreement",
    "agreement_seller": "sign the transfer agreement",
    "medical": "record the medical",
    "registration": "submit the registration",
}


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _player(card: dict, player) -> dict:
    card.update(
        player_id=player.id, player_name=player.name,
        player_position=getattr(player.position, "value", player.position),
        player_photo_url=getattr(player, "photo_url", None),
    )
    return card


@dataclass
class _Entry:
    card: BoardCard

    @property
    def sort_key(self):
        c = self.card
        # Furthest column first, then your move, then most recent.
        return (RANK.get(c.column, -1), c.whose_move == WhoseMove.YOUR, _aware(c.updated_at) or datetime.min.replace(tzinfo=timezone.utc))


def _money(v) -> str:
    n = float(v)
    return f"£{n / 1e6:.1f}m".replace(".0m", "m") if n >= 1e6 else f"£{round(n / 1e3)}k"


async def _offer_cards(db: AsyncSession, club_id: uuid.UUID, now: datetime, history: bool = False) -> list[BoardCard]:
    offers, _ = await offers_service.list_offers(db, club_id=club_id, direction="all", page=1, page_size=_PAGE)
    cards = []
    for o in offers:
        if o.status in (OfferStatus.DRAFT, OfferStatus.ACCEPTED) or o.player is None:
            continue  # an accepted offer is shown as its deal
        buying = str(o.from_club_id) == str(club_id)
        other = o.to_club.name if (buying and o.to_club) else (None if buying else buyer_name(o, o.from_club, club_id))
        open_ = o.status in (OfferStatus.SENT, OfferStatus.COUNTERED)
        updated = _aware(o.last_action_at) or _aware(o.created_at)
        if not open_ and not history and (updated is None or now - updated > CLOSED_FOR):
            continue
        move = offers_service.compute_offer_whose_move(o, club_id) if open_ else WhoseMove.NEITHER
        if open_:
            detail = ("Countered" if o.status == OfferStatus.COUNTERED else ("Offer sent" if buying else "Offer received"))
            detail += " · your move" if move == WhoseMove.YOUR else f" · waiting on {other or 'them'}"
        else:
            detail = {"REJECTED": "Offer rejected", "WITHDRAWN": "Offer withdrawn", "EXPIRED": "Offer expired"}[o.status.value]
        cards.append(BoardCard(**_player(dict(
            key=f"{'BUYING' if buying else 'SELLING'}:{o.player_id}", side="BUYING" if buying else "SELLING",
            column="offers" if open_ else "closed", kind="offer", entity_id=o.id, counterparty=other,
            amount=o.loan_fee if getattr(o.deal_type, "value", o.deal_type) == "LOAN" else o.fee_amount,
            detail=detail, whose_move=move, deadline=o.expires_at if open_ else None,
            link=f"/offers/{o.id}", updated_at=updated,
        ), o.player)))
    return cards


async def _deal_cards(db: AsyncSession, club_id: uuid.UUID, now: datetime, history: bool = False) -> list[BoardCard]:
    deals, _ = await deals_service.list_deals(db, club_id=club_id, page=1, page_size=_PAGE)
    cards = []
    for d in deals:
        if d.player is None:
            continue
        buying = str(d.buyer_club_id) == str(club_id)
        other_club = d.seller_club if buying else d.buyer_club
        other = other_club.name if other_club else None
        updated = _aware(d.updated_at)
        if d.status == DealStatus.COLLAPSED:
            if not history and (updated is None or now - updated > CLOSED_FOR):
                continue
            column, move, detail = "closed", WhoseMove.NEITHER, "Deal collapsed"
        elif d.status == DealStatus.COMPLETED or d.stage == DealStage.COMPLETED:
            if not history and updated is not None and now - updated > DONE_FOR:
                continue
            column, move, detail = "done", WhoseMove.NEITHER, "Transfer complete"
        else:
            column = DEAL_COLUMN.get(d.stage, "fee_agreed")
            move = deals_service.compute_deal_whose_move(d, club_id)
            outstanding = deals_service.outstanding_paperwork_for(d, club_id)
            if d.stage == DealStage.CONFIRMED:
                detail = "Signature" + (" · your move" if move == WhoseMove.YOUR else f" · waiting on {other or 'them'}")
            elif outstanding:
                detail = f"You: {_PAPERWORK.get(outstanding[0], 'paperwork')}"
            elif d.stage == DealStage.AGENT_NEGOTIATION:
                detail = "Agent negotiation"
            elif d.stage == DealStage.PERSONAL_TERMS:
                detail = "Personal terms" + (" · your move" if move == WhoseMove.YOUR else "")
            elif d.stage == DealStage.PAPERWORK:
                detail = f"Paperwork · waiting on {other or 'them'}"
            else:
                detail = "Fee agreed" + (" · your move" if move == WhoseMove.YOUR else "")
        cards.append(BoardCard(**_player(dict(
            key=f"{'BUYING' if buying else 'SELLING'}:{d.player_id}", side="BUYING" if buying else "SELLING",
            column=column, kind="deal", entity_id=d.id, counterparty=other, amount=d.agreed_fee,
            detail=detail, whose_move=move, link=f"/deals/{d.id}", updated_at=updated,
        ), d.player)))
    return cards


async def _enquiry_cards(db: AsyncSession, club_id: uuid.UUID, now: datetime, history: bool = False) -> list[BoardCard]:
    from app.enquiries import service as enquiries_service
    from app.enquiries.models import EnquiryStatus

    cards = []
    for e in await enquiries_service.list_enquiries(db, club_id):
        if e.player is None:
            continue
        # A closed enquiry either became an offer or went nowhere: the board
        # shows only open ones; history shows every one.
        if e.status != EnquiryStatus.OPEN and not history:
            continue
        resp = enquiries_service.to_response(e, club_id, with_messages=False)
        selling = resp.role == "owning"
        other = (resp.asking_club if selling else resp.owning_club).name
        open_ = e.status == EnquiryStatus.OPEN
        move = enquiries_service.whose_move(e, club_id) if open_ else WhoseMove.NEITHER
        detail = ("Enquiry" + (" · your reply" if move == WhoseMove.YOUR else f" · waiting on {other}")) if open_ else "Enquiry closed"
        cards.append(BoardCard(**_player(dict(
            key=f"{'SELLING' if selling else 'BUYING'}:{e.player_id}", side="SELLING" if selling else "BUYING",
            column="talking" if open_ else "closed", kind="enquiry", entity_id=e.id, counterparty=other,
            detail=detail, whose_move=move, link=f"/enquiries/{e.id}", updated_at=_aware(e.updated_at),
        ), e.player)))
    return cards


async def _listing_cards(db: AsyncSession, club_id: uuid.UUID, now: datetime, history: bool = False) -> list[BoardCard]:
    cards = []
    sales, _ = await sales_service.list_sales(db, seller_club_id=club_id, page=1, page_size=_PAGE)
    for s in sales:
        if s.player is None or s.status == SaleStatus.CLOSED:
            continue  # sold: shown as its deal
        updated = _aware(s.updated_at)
        base = dict(key=f"SELLING:{s.player_id}", side="SELLING", entity_id=s.id, link=f"/sales/{s.id}",
                    updated_at=updated)
        if s.status != SaleStatus.OPEN:
            if not history and (updated is None or now - updated > CLOSED_FOR):
                continue
            cards.append(BoardCard(**_player(dict(
                base, column="closed", kind="listing",
                detail="Listing withdrawn" if s.status == SaleStatus.WITHDRAWN else "Listing expired",
            ), s.player)))
            continue
        active = [b for b in (s.bids or []) if b.status == BidStatus.ACTIVE]
        if s.sale_type == SaleType.AUCTION and active:
            best = sales_service.get_best_bid_amount(s.bids or [])
            move = sales_service.compute_sale_whose_move(
                bid_count=len(active), reserve_met=sales_service.is_reserve_met(s), deadline=s.deadline,
            )
            cards.append(BoardCard(**_player(dict(
                base, column="offers", kind="bid", amount=best,
                detail=f"{len(active)} bid{'s' if len(active) != 1 else ''} · best {_money(best)}",
                whose_move=move, deadline=s.deadline,
            ), s.player)))
        else:
            kind = {SaleType.AUCTION: "Auction", SaleType.FIXED_PRICE: "Fixed price"}.get(s.sale_type, "Listed")
            cards.append(BoardCard(**_player(dict(
                base, column="talking", kind="listing", amount=s.asking_price,
                detail=f"{kind} · no offers yet", deadline=s.deadline,
            ), s.player)))

    # Bids this club placed on other clubs' auctions.
    rows = await db.execute(
        select(Bid).where(Bid.buyer_club_id == club_id, Bid.status == BidStatus.ACTIVE)
        .options(selectinload(Bid.sale).selectinload(Sale.player), selectinload(Bid.sale).selectinload(Sale.seller_club),
                 selectinload(Bid.sale).selectinload(Sale.bids))
    )
    for b in rows.scalars():
        s = b.sale
        if s is None or s.player is None or s.status != SaleStatus.OPEN:
            continue
        best = sales_service.get_best_bid_amount(s.bids or [])
        leading = best is not None and b.amount >= best
        cards.append(BoardCard(**_player(dict(
            key=f"BUYING:{s.player_id}", side="BUYING", column="offers", kind="bid", entity_id=s.id,
            counterparty=s.seller_club.name if s.seller_club else None, amount=b.amount,
            detail="Your bid · leading" if leading else f"Your bid · outbid at {_money(best)}",
            whose_move=WhoseMove.THEIR if leading else WhoseMove.YOUR, deadline=s.deadline,
            link=f"/sales/{s.id}", updated_at=_aware(getattr(b, "updated_at", None) or getattr(b, "created_at", None)),
        ), s.player)))
    return cards


async def get_board(db: AsyncSession, club_id: uuid.UUID, side: str = "BOTH") -> BoardResponse:
    now = datetime.now(timezone.utc)
    all_cards = (
        await _deal_cards(db, club_id, now) + await _offer_cards(db, club_id, now)
        + await _enquiry_cards(db, club_id, now) + await _listing_cards(db, club_id, now)
    )
    if side in ("BUYING", "SELLING"):
        all_cards = [c for c in all_cards if c.side == side]

    active: dict[str, list[BoardCard]] = {}
    closed: dict[str, list[BoardCard]] = {}
    for c in all_cards:
        (closed if c.column == "closed" else active).setdefault(c.key, []).append(c)

    shown: list[BoardCard] = []
    for key, cards in active.items():
        cards.sort(key=lambda c: _Entry(c).sort_key, reverse=True)
        top = cards[0]
        top.others = sum(1 for c in cards[1:] if c.column == top.column)
        shown.append(top)
    drawer = []
    for key, cards in closed.items():
        if key in active:
            continue  # active again on this side: the live card is enough
        cards.sort(key=lambda c: _aware(c.updated_at) or now, reverse=True)
        drawer.append(cards[0])

    def order(c: BoardCard):
        # Your move first, then soonest deadline, then most recent.
        return (c.whose_move != WhoseMove.YOUR, _aware(c.deadline) or datetime.max.replace(tzinfo=timezone.utc),
                -(_aware(c.updated_at) or now).timestamp())

    columns = [
        BoardColumn(key=k, label=label, cards=sorted([c for c in shown if c.column == k], key=order))
        for k, label in COLUMNS
    ]
    drawer.sort(key=lambda c: _aware(c.updated_at) or now, reverse=True)
    return BoardResponse(
        columns=columns,
        closed=drawer,
        counts={
            "buying": sum(c.side == "BUYING" for c in shown),
            "selling": sum(c.side == "SELLING" for c in shown),
            "your_move": sum(c.whose_move == WhoseMove.YOUR for c in shown),
        },
    )


HISTORY_OUTCOMES = {"completed": "done", "ended": "closed"}


async def get_history(
    db: AsyncSession, club_id: uuid.UUID, *, side: str = "BOTH", q: str | None = None,
    outcome: str | None = None, page: int = 1, page_size: int = 30,
) -> dict:
    """Every transfer that finished or went nowhere, newest first: completed
    deals, collapsed deals, offers rejected, withdrawn or expired, closed
    enquiries and ended listings. One row per item, not per player."""
    now = datetime.now(timezone.utc)
    cards = (
        await _deal_cards(db, club_id, now, history=True) + await _offer_cards(db, club_id, now, history=True)
        + await _enquiry_cards(db, club_id, now, history=True) + await _listing_cards(db, club_id, now, history=True)
    )
    cards = [c for c in cards if c.column in ("done", "closed")]
    if side in ("BUYING", "SELLING"):
        cards = [c for c in cards if c.side == side]
    if outcome in HISTORY_OUTCOMES:
        cards = [c for c in cards if c.column == HISTORY_OUTCOMES[outcome]]
    if q and q.strip():
        needle = q.strip().lower()
        cards = [c for c in cards if needle in c.player_name.lower() or needle in (c.counterparty or "").lower()]
    cards.sort(key=lambda c: _aware(c.updated_at) or now, reverse=True)
    start = (max(page, 1) - 1) * page_size
    return {"items": cards[start:start + page_size], "total": len(cards), "page": page, "page_size": page_size}
