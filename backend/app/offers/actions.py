"""Offer actions: what making, countering, raising, accepting, rejecting and
withdrawing an offer does, beyond the offer row itself (offers/service.py).

Each action runs the guards, captures an approval when the club's policy
asks for one, notifies the other side, records AI-assisted use, commits, and
pushes the live update. The HTTP endpoints (offers/router.py) and Lite's held
sends (lite/held.py) both call these, so the two can't drift apart. Errors
are `OfferActionError` with the HTTP status the endpoint should return.
"""
import uuid
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.approvals import service as approvals_service
from app.approvals.models import ApprovalActionType
from app.auth.models import User
from app.deals.models import DealType
from app.notifications import copy as push_copy
from app.notifications import service as notif_service
from app.notifications.models import NotificationType
from app.offers import service
from app.offers.schemas import OfferCounterRequest, OfferCreateRequest, OfferImproveRequest
from app.transfer_window import service as window_service
from app.ws.manager import manager as ws_manager


class OfferActionError(Exception):
    def __init__(self, status_code: int, detail):
        super().__init__(str(detail))
        self.status_code = status_code
        self.detail = detail


@dataclass
class ActionResult:
    """What happened: the offer (re-read), the deal an acceptance created, or
    the approval captured instead of acting."""
    offer: object | None = None
    deal: object | None = None
    approval: object | None = None


# ── Shared helpers ────────────────────────────────────────────────────────────


async def notify_offer(
    db: AsyncSession, offer, *, recipient_club_id, ntype: NotificationType, message: str, push: dict | None = None,
) -> None:
    """Create DB notifications for an offer event, role-routed per club
    (TRA-152). Must be called before commit. `push` is the push wording
    from app.notifications.copy."""
    if recipient_club_id is None:
        return
    # The club on the other side, for the notification's crest and link;
    # never an anonymous buyer while he is still masked from the seller.
    from app.common.masking import buyer_is_masked

    other = offer.from_club_id if str(recipient_club_id) == str(offer.to_club_id) else offer.to_club_id
    if other == offer.from_club_id and buyer_is_masked(offer, recipient_club_id):
        other = None
    await notif_service.notify_club(
        db, uuid.UUID(str(recipient_club_id)), type=ntype, message=message, link=f"/offers/{offer.id}",
        related_player_id=offer.player_id, related_club_id=other, **(push or {}),
    )


async def _notify_player_of_offer(db: AsyncSession, offer) -> None:
    """TRA-76: if the player has their own login, let them know a club has made an offer."""
    from app.auth.models import PlayerProfile

    player_profile = (await db.execute(
        select(PlayerProfile).where(PlayerProfile.player_id == offer.player_id)
    )).scalar_one_or_none()
    if player_profile is None:
        return
    await notif_service.create_notification(
        db, recipient_user_id=player_profile.user_id, type=NotificationType.OFFER_RECEIVED,
        message="A club has made an offer for your transfer", link="/player/profile",
        related_player_id=offer.player_id,
    )


async def broadcast(db: AsyncSession, offer_id: uuid.UUID) -> None:
    """Push OFFER_UPDATED to every member of both parties of an offer."""
    offer = await service.get_offer_by_id(db, offer_id)
    if offer is None:
        return
    user_ids: list[uuid.UUID] = []
    for club_id in [offer.from_club_id, offer.to_club_id]:
        if club_id is None:
            continue
        user_ids += await notif_service.club_member_user_ids(db, uuid.UUID(str(club_id)))
    await ws_manager.broadcast_to_users(list(set(user_ids)), {"type": "OFFER_UPDATED", "id": str(offer_id)})


def _fee_summary(fee: Decimal | None) -> str:
    """Approval summaries name a figure, but an offer can legitimately carry no
    transfer fee (free transfer, loan, swap). Formatting None with `:,.0f`
    raises, and because the summary is built as an argument to `maybe_capture`
    it raised for *every* caller, not just the MANAGER role that check targets.
    """
    return f"£{fee:,.0f}" if fee is not None else "no fee"


def terms_summary(
    *, deal_type: DealType, fee_amount: Decimal | None, loan_fee: Decimal | None,
    option_to_buy: Decimal | None, obligation_to_buy: bool,
) -> str:
    """What an approver is being asked to sign off. A loan has to say it is a
    loan and name any purchase clause — "no fee" alone would describe an
    obligation to buy at £18m as costing nothing."""
    if deal_type != DealType.LOAN:
        return _fee_summary(fee_amount)
    parts = [f"loan, {_fee_summary(loan_fee)} loan fee" if loan_fee else "loan, no loan fee"]
    if option_to_buy is not None:
        kind = "obligation" if obligation_to_buy else "option"
        parts.append(f"{kind} to buy at £{option_to_buy:,.0f}")
    return ", ".join(parts)


async def audit_ai_used(db: AsyncSession, *, entity_type: str, entity_id, user: User, feature: str,
                        description: str, ref=None) -> None:
    """The action started from the assistant's suggestion (ADR 0006): recorded,
    never binding, and counted as used (ai/tracking.py) against `ref`, the
    subject the suggestion was shown for."""
    from app.ai import tracking
    from app.audit import service as audit_service

    await audit_service.emit(
        db, entity_type=entity_type, entity_id=entity_id, action="AI_SUGGESTION_USED",
        actor_user_id=user.id, payload={"feature": feature}, description=description,
    )
    await tracking.record_used(db, feature, user.id, ref=ref if ref is not None else entity_id)


async def _reread(db: AsyncSession, offer) -> object:
    # The session does not expire on commit, so a re-read would hand back the
    # copy already loaded — its events and messages as they were before this
    # change. Expire just this offer: populate_existing on the query also
    # refreshed the clubs loaded with it and dropped their loaded finance,
    # which the approval check then lazy-loaded and crashed on.
    offer_id = offer.id
    db.expire(offer)
    return await service.get_offer_by_id(db, offer_id)


async def _player_name(db: AsyncSession, player_id) -> str:
    from app.players import service as players_service

    player = await players_service.get_player_by_id(db, player_id)
    return player.name if player else "a player"


# ── Make an offer ─────────────────────────────────────────────────────────────


async def create_offer(db: AsyncSession, user: User, club, body: OfferCreateRequest) -> ActionResult:
    if not user.is_superuser and not await window_service.is_transfer_allowed(db):
        raise OfferActionError(403, "Transfer window is closed. Offers cannot be made outside of a transfer window.")

    # Guard: one active offer per (buyer, player) at a time
    existing = await service.get_active_offer_for_buyer(db, body.player_id, club.id)
    if existing:
        raise OfferActionError(
            409, {"message": "You already have an active offer for this player.", "offer_id": str(existing.id)},
        )

    # Guard: cannot make offers while a deal is already in progress for this player
    from app.deals import service as deals_service

    active_deal = await deals_service.get_active_deal_for_player(db, body.player_id)
    if active_deal and active_deal.status == "IN_PROGRESS":
        raise OfferActionError(
            409, "This player already has a transfer deal in progress. New offers cannot be made at this time.",
        )

    # The offer's own terms too, before any approval is captured: an approver
    # should never be asked to sign off an offer that could not be sent.
    try:
        await service.check_new_offer(
            db, player_id=body.player_id, deal_type=body.deal_type, fee_amount=body.fee_amount,
            wage_weekly=body.wage_weekly, loan_start=body.loan_start, loan_end=body.loan_end,
            loan_fee=body.loan_fee, wage_split_pct=body.wage_split_pct, option_to_buy=body.option_to_buy,
            obligation_to_buy=body.obligation_to_buy, recall_allowed=body.recall_allowed,
            no_fee_reason=body.no_fee_reason, obligation_conditions=body.obligation_conditions,
            sale_id=body.sale_id, instalments=body.instalments, clauses=body.clauses, sell_on_pct=body.sell_on_pct,
        )
    except ValueError as exc:
        raise OfferActionError(400, str(exc))

    # Phase 5 (D7): a MANAGER's offer at/above the club threshold is captured
    # as a pending approval after the guards above — nothing executed yet.
    terms = dict(
        deal_type=body.deal_type, fee_amount=body.fee_amount, loan_fee=body.loan_fee,
        option_to_buy=body.option_to_buy, obligation_to_buy=body.obligation_to_buy,
    )
    approval = await approvals_service.maybe_capture(
        db, current_user=user, club=club, action_type=ApprovalActionType.CREATE_OFFER,
        amount=service.approval_amount(**terms, clauses=body.clauses),
        # Everything the offer is, so the approved replay creates this offer
        # and not a permanent, named one: before the loan terms and the
        # anonymity flag were carried here, approving an anonymous offer sent
        # it with the buyer named.
        payload={
            "player_id": str(body.player_id),
            "to_club_id": str(body.to_club_id) if body.to_club_id else None,
            "sale_id": str(body.sale_id) if body.sale_id else None,
            "fee_amount": str(body.fee_amount) if body.fee_amount is not None else None,
            "wage_weekly": str(body.wage_weekly) if body.wage_weekly else None,
            "contract_years": body.contract_years,
            "contract_end_date": body.contract_end_date.isoformat() if body.contract_end_date else None,
            "add_ons": body.add_ons,
            "expires_at": body.expires_at.isoformat() if body.expires_at else None,
            "is_anonymous": body.is_anonymous,
            "deal_type": body.deal_type.value,
            "loan_start": body.loan_start.isoformat() if body.loan_start else None,
            "loan_end": body.loan_end.isoformat() if body.loan_end else None,
            "loan_fee": str(body.loan_fee) if body.loan_fee is not None else None,
            "wage_split_pct": str(body.wage_split_pct) if body.wage_split_pct is not None else None,
            "option_to_buy": str(body.option_to_buy) if body.option_to_buy is not None else None,
            "obligation_to_buy": body.obligation_to_buy,
            "recall_allowed": body.recall_allowed,
            "no_fee_reason": body.no_fee_reason,
            "obligation_conditions": body.obligation_conditions,
            "instalments": [i.model_dump(mode="json") for i in body.instalments],
            "clauses": [c.model_dump(mode="json") for c in body.clauses],
            "sell_on_pct": str(body.sell_on_pct) if body.sell_on_pct is not None else None,
        },
        summary=f"Offer for {await _player_name(db, body.player_id)} — {terms_summary(**terms)}",
    )
    if approval is not None:
        if body.ai_assisted:
            await audit_ai_used(db, entity_type="APPROVAL", entity_id=approval.id, user=user,
                                feature="ask_proposal", description="Offer started from the assistant's suggestion",
                                ref=body.player_id)
        await db.commit()
        return ActionResult(approval=approval)

    try:
        offer = await service.create_offer(
            db, player_id=body.player_id, from_club_id=club.id, to_club_id=body.to_club_id, sale_id=body.sale_id,
            fee_amount=body.fee_amount, wage_weekly=body.wage_weekly, contract_years=body.contract_years,
            contract_end_date=body.contract_end_date, add_ons=body.add_ons, expires_at=body.expires_at,
            is_anonymous=body.is_anonymous, deal_type=body.deal_type, loan_start=body.loan_start,
            loan_end=body.loan_end, loan_fee=body.loan_fee, wage_split_pct=body.wage_split_pct,
            option_to_buy=body.option_to_buy, obligation_to_buy=body.obligation_to_buy,
            recall_allowed=body.recall_allowed, no_fee_reason=body.no_fee_reason,
            obligation_conditions=body.obligation_conditions, instalments=body.instalments,
            clauses=body.clauses, sell_on_pct=body.sell_on_pct,
        )
        await notify_offer(
            db, offer, recipient_club_id=offer.to_club_id, ntype=NotificationType.OFFER_RECEIVED,
            message="You have received a new offer", push=await push_copy.offer_received(db, offer),
        )
        await _notify_player_of_offer(db, offer)
        if body.ai_assisted:
            await audit_ai_used(db, entity_type="OFFER", entity_id=offer.id, user=user,
                                feature="ask_proposal", description="Offer started from the assistant's suggestion",
                                ref=body.player_id)
        await db.commit()
    except ValueError as exc:
        await db.rollback()
        raise OfferActionError(400, str(exc))

    offer = await service.get_offer_by_id(db, offer.id)
    await broadcast(db, offer.id)
    return ActionResult(offer=offer)


# ── Counter and raise ─────────────────────────────────────────────────────────


async def counter_offer(db: AsyncSession, user: User, club, offer, body: OfferCounterRequest) -> ActionResult:
    previous = push_copy.offer_amount(offer)[0]
    try:
        await service.counter_offer(
            db, offer, actor_club_id=club.id, fee_amount=body.fee_amount, wage_weekly=body.wage_weekly,
            contract_years=body.contract_years, contract_end_date=body.contract_end_date, add_ons=body.add_ons,
            expires_at=body.expires_at, loan_start=body.loan_start, loan_end=body.loan_end, loan_fee=body.loan_fee,
            wage_split_pct=body.wage_split_pct, option_to_buy=body.option_to_buy,
            obligation_to_buy=body.obligation_to_buy, recall_allowed=body.recall_allowed,
            obligation_conditions=body.obligation_conditions,
            # Sent as an explicit null, as opposed to left out: remove it.
            remove_option_to_buy=("option_to_buy" in body.model_fields_set and body.option_to_buy is None),
            instalments=body.instalments, clauses=body.clauses, sell_on_pct=body.sell_on_pct,
            remove_sell_on=("sell_on_pct" in body.model_fields_set and body.sell_on_pct is None),
        )
        other_club_id = offer.to_club_id if offer.from_club_id == club.id else offer.from_club_id
        await notify_offer(
            db, offer, recipient_club_id=other_club_id, ntype=NotificationType.OFFER_COUNTERED,
            message="A counter offer has been submitted",
            push=await push_copy.offer_countered(db, offer, recipient_club_id=other_club_id, previous=previous),
        )
        if body.ai_assisted:
            await audit_ai_used(db, entity_type="OFFER", entity_id=offer.id, user=user,
                                feature=body.ai_feature or "counter_advisor",
                                description="Counter offer started from the assistant's suggestion", ref=offer.id)
        await db.commit()
    except ValueError as exc:
        await db.rollback()
        raise OfferActionError(400, str(exc))

    offer = await _reread(db, offer)
    await broadcast(db, offer.id)
    return ActionResult(offer=offer)


async def improve_offer(db: AsyncSession, user: User, club, offer, body: OfferImproveRequest) -> ActionResult:
    """Item 2: the buyer raises their own pending offer without waiting for a reply."""
    previous = push_copy.offer_amount(offer)[0]
    try:
        await service.improve_own_offer(
            db, offer, actor_club_id=club.id, fee_amount=body.fee_amount, wage_weekly=body.wage_weekly,
            add_ons=body.add_ons, loan_fee=body.loan_fee,
        )
        await notify_offer(
            db, offer, recipient_club_id=offer.to_club_id, ntype=NotificationType.OFFER_COUNTERED,
            message="The buyer has raised their offer",
            push=await push_copy.offer_countered(db, offer, recipient_club_id=offer.to_club_id, previous=previous, raised=True),
        )
        await db.commit()
    except ValueError as exc:
        await db.rollback()
        raise OfferActionError(400, str(exc))

    offer = await _reread(db, offer)
    await broadcast(db, offer.id)
    return ActionResult(offer=offer)


# ── Accept, reject, withdraw ──────────────────────────────────────────────────


async def accept_offer(db: AsyncSession, user: User, club, offer, *, ai_assisted: bool = False) -> ActionResult:
    # Phase 5 (D7): a MANAGER accepting an offer at/above the club threshold is
    # captured as a pending approval instead of executing.
    terms = dict(
        deal_type=offer.deal_type, fee_amount=offer.fee_amount, loan_fee=offer.loan_fee,
        option_to_buy=offer.option_to_buy, obligation_to_buy=offer.obligation_to_buy,
    )
    approval = await approvals_service.maybe_capture(
        db, current_user=user, club=club, action_type=ApprovalActionType.ACCEPT_OFFER,
        amount=service.approval_amount(**terms, clauses=offer.clauses),
        payload={"offer_id": str(offer.id)},
        summary=f"Accept offer for {await _player_name(db, offer.player_id)} — {terms_summary(**terms)}",
    )
    if approval is not None:
        if ai_assisted:
            await audit_ai_used(db, entity_type="APPROVAL", entity_id=approval.id, user=user,
                                feature="ask_proposal", description="Acceptance started from the assistant's suggestion",
                                ref=offer.id)
        await db.commit()
        return ActionResult(approval=approval)

    try:
        deal = await service.accept_offer(db, offer, actor_club_id=club.id)
        await notify_offer(
            db, offer, recipient_club_id=offer.from_club_id, ntype=NotificationType.OFFER_ACCEPTED,
            message="Your offer has been accepted",
        )
        if ai_assisted:
            await audit_ai_used(db, entity_type="OFFER", entity_id=offer.id, user=user,
                                feature="ask_proposal", description="Acceptance started from the assistant's suggestion",
                                ref=offer.id)
        await db.commit()
        await db.refresh(deal)
    except ValueError as exc:
        await db.rollback()
        raise OfferActionError(400, str(exc))

    await broadcast(db, offer.id)
    return ActionResult(offer=offer, deal=deal)


async def reject_offer(db: AsyncSession, user: User, club, offer, *, ai_assisted: bool = False) -> ActionResult:
    offer_id = offer.id
    try:
        await service.reject_offer(db, offer, actor_club_id=club.id)
        await notify_offer(
            db, offer, recipient_club_id=offer.from_club_id, ntype=NotificationType.OFFER_REJECTED,
            message="Your offer has been rejected",
        )
        if ai_assisted:
            await audit_ai_used(db, entity_type="OFFER", entity_id=offer.id, user=user,
                                feature="ask_proposal", description="Rejection started from the assistant's suggestion",
                                ref=offer.id)
        await db.commit()
    except ValueError as exc:
        await db.rollback()
        raise OfferActionError(400, str(exc))

    offer = await service.get_offer_by_id(db, offer_id)
    await broadcast(db, offer_id)
    return ActionResult(offer=offer)


async def withdraw_offer(db: AsyncSession, user: User, club, offer) -> ActionResult:
    offer_id = offer.id
    try:
        await service.withdraw_offer(db, offer, actor_club_id=club.id)
        other_club_id = offer.to_club_id if offer.from_club_id == club.id else offer.from_club_id
        await notify_offer(
            db, offer, recipient_club_id=other_club_id, ntype=NotificationType.OFFER_WITHDRAWN,
            message="An offer has been withdrawn",
        )
        await db.commit()
    except ValueError as exc:
        await db.rollback()
        raise OfferActionError(400, str(exc))

    offer = await service.get_offer_by_id(db, offer_id)
    await broadcast(db, offer_id)
    return ActionResult(offer=offer)


# ── Messages ──────────────────────────────────────────────────────────────────


async def add_message(db: AsyncSession, user: User, club, offer, body: str):
    """A message on the offer, to the other club. Returns the message."""
    try:
        msg = await service.add_message(db, offer, sender_club_id=club.id, body=body)
        other_club_id = offer.to_club_id if offer.from_club_id == club.id else offer.from_club_id
        await notify_offer(
            db, offer, recipient_club_id=other_club_id, ntype=NotificationType.OFFER_MESSAGE,
            message="New message in your negotiation",
            push=await push_copy.offer_message(db, offer, sender_club_id=club.id, text=body),
        )
        await db.commit()
        await db.refresh(msg)
    except ValueError as exc:
        await db.rollback()
        raise OfferActionError(400, str(exc))
    await broadcast(db, offer.id)
    return msg
