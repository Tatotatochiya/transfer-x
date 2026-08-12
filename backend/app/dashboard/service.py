"""B2 — Dashboard aggregate: waiting-on-you items across offers, deals, sales
and approvals in one ranked response, replacing DashboardPage.tsx's 5-query
client-side concat. Reuses each module's own service-layer read functions
(offers/deals/sales/approvals) rather than querying their models directly —
cross-module needs go through the service layer, not model internals.
"""

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.approvals import service as approvals_service
from app.approvals.models import ApprovalStatus
from app.auth.models import User
from app.clubs.capabilities import Capability, ensure_club_capability
from app.clubs.models import Club
from app.common.schemas import WhoseMove
from app.dashboard.schemas import DashboardItem, DashboardResponse
from app.deals import service as deals_service
from app.deals.models import Deal, DealStage
from app.offers import service as offers_service
from app.offers.models import Offer, OfferStatus
from app.sales import service as sales_service
from app.sales.models import BidStatus, SaleStatus

# Bounds each per-entity candidate fetch — a club's simultaneously-open offers/
# deals/sales realistically stays well under this; if it ever doesn't, the fix
# is a real "non-terminal only" query, not raising this number.
_CANDIDATE_PAGE_SIZE = 200


async def _approval_items(
    db: AsyncSession, club_id: uuid.UUID, current_user: User
) -> list[tuple[datetime, DashboardItem]]:
    try:
        await ensure_club_capability(db, current_user, Capability.APPROVE_ACTIONS)
        requester_filter = None
    except HTTPException:
        # Mirrors GET /clubs/me/approvals exactly: without APPROVE_ACTIONS, a
        # member only ever sees their own pending requests, not the full queue.
        requester_filter = current_user.id

    approvals = await approvals_service.list_approvals(
        db, club_id, status=ApprovalStatus.PENDING, requested_by_user_id=requester_filter
    )
    return [
        (
            a.created_at,
            DashboardItem(
                kind="approval",
                id=a.id,
                amount=a.amount,
                reason=a.summary or "Approval pending your decision",
                link="/approvals",
            ),
        )
        for a in approvals
    ]


def _offer_reason(offer: Offer) -> str:
    return "Countered — your response needed" if offer.status == OfferStatus.COUNTERED else "Offer received — awaiting your response"


async def _offer_items(db: AsyncSession, club_id: uuid.UUID) -> list[tuple[datetime, DashboardItem]]:
    offers, _ = await offers_service.list_offers(
        db, club_id=club_id, direction="all", page=1, page_size=_CANDIDATE_PAGE_SIZE
    )
    out = []
    for o in offers:
        if offers_service.compute_offer_whose_move(o, club_id) != WhoseMove.YOUR:
            continue
        counterparty = o.to_club if o.from_club_id == club_id else o.from_club
        out.append((
            o.last_action_at,
            DashboardItem(
                kind="offer",
                id=o.id,
                player_name=o.player.name if o.player else None,
                club_name=counterparty.name if counterparty else None,
                amount=o.fee_amount,
                reason=_offer_reason(o),
                link=f"/offers/{o.id}",
            ),
        ))
    return out


def _deal_reason(deal: Deal) -> str:
    """Mirrors dealWhoseMoveReason() in frontend/src/lib/whoseMove.ts for the
    two stages that can actually reach here (whose_move already == YOUR)."""
    if deal.stage == DealStage.CONFIRMED:
        return "You — signature"
    updated_at = deal.updated_at
    if updated_at.tzinfo is None:  # SQLite drops tzinfo
        updated_at = updated_at.replace(tzinfo=timezone.utc)
    days = int((datetime.now(timezone.utc) - updated_at).total_seconds() // 86400)
    return f"Agent — {days} day{'s' if days != 1 else ''} idle"


async def _deal_items(db: AsyncSession, club_id: uuid.UUID) -> list[tuple[datetime, DashboardItem]]:
    deals, _ = await deals_service.list_deals(db, club_id=club_id, page=1, page_size=_CANDIDATE_PAGE_SIZE)
    out = []
    for d in deals:
        if deals_service.compute_deal_whose_move(d) != WhoseMove.YOUR:
            continue
        counterparty = d.seller_club if d.buyer_club_id == club_id else d.buyer_club
        out.append((
            d.updated_at,
            DashboardItem(
                kind="deal",
                id=d.id,
                player_name=d.player.name if d.player else None,
                club_name=counterparty.name if counterparty else None,
                amount=d.agreed_fee,
                reason=_deal_reason(d),
                link=f"/deals/{d.id}",
            ),
        ))
    return out


async def _sale_items(db: AsyncSession, club_id: uuid.UUID) -> list[tuple[datetime, DashboardItem]]:
    # whose_move is inherently seller-side for sales (TRA-139) — only this
    # club's own listings can ever produce a "your move" auction item.
    sales, _ = await sales_service.list_sales(
        db, seller_club_id=club_id, status=SaleStatus.OPEN, page=1, page_size=_CANDIDATE_PAGE_SIZE
    )
    out = []
    for s in sales:
        active_bids = [b for b in (s.bids or []) if b.status == BidStatus.ACTIVE]
        bid_count = len(active_bids)
        reserve_ok = sales_service.is_reserve_met(s) if s.bids is not None else False
        whose_move = sales_service.compute_sale_whose_move(
            bid_count=bid_count, reserve_met=reserve_ok, deadline=s.deadline
        )
        if whose_move != WhoseMove.YOUR:
            continue
        best = sales_service.get_best_bid_amount(s.bids or [])
        out.append((
            s.deadline,
            DashboardItem(
                kind="sale",
                id=s.id,
                player_name=s.player.name if s.player else None,
                amount=best,
                reason="Reserve met — auction closing soon",
                link=f"/sales/{s.id}",
            ),
        ))
    return out


async def get_dashboard(db: AsyncSession, *, club: Club, current_user: User) -> DashboardResponse:
    approval_pairs = await _approval_items(db, club.id, current_user)
    offer_pairs = await _offer_items(db, club.id)
    deal_pairs = await _deal_items(db, club.id)
    sale_pairs = await _sale_items(db, club.id)

    # Priority order: approvals and confirmed deals block the single most
    # concrete next step; offers are still mid-negotiation; sales are only
    # urgent right at closing. Within a kind, oldest-waiting (or
    # soonest-closing, for sales) first.
    waiting_on_you = (
        [item for _, item in sorted(approval_pairs, key=lambda p: p[0])]
        + [item for _, item in sorted(deal_pairs, key=lambda p: p[0])]
        + [item for _, item in sorted(offer_pairs, key=lambda p: p[0])]
        + [item for _, item in sorted(sale_pairs, key=lambda p: p[0])]
    )
    return DashboardResponse(waiting_on_you=waiting_on_you)
