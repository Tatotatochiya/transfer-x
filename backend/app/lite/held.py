"""Held sends for undo, and plain progress (Lite L6; architecture ADR 0007).

A confirmed Lite action is not sent straight away. `hold` checks it now, so
a problem shows on the card, and stores it HELD for HOLD_SECONDS. Undoing
in that window leaves no trace for the other club: nothing has been sent,
notified, emailed or reserved. When the window closes, `execute_due` runs
the normal offers endpoint as the user who confirmed it, so the action takes
exactly the path a full-app click takes: guards, approval capture, budget
reservation, notifications, audit.

The checks at hold time are the endpoints' own rules, read without side
effects (the endpoints themselves notify and email, so they can't be
dry-run). If something changes in the ten seconds (the other club replies,
the window shuts), the endpoint refuses it when it runs, and the action ends
FAILED with the endpoint's reason.

`progress` turns the action, its offer and any deal into five plain steps
for the Sent screen. The current step's hint comes from `assist.deal_steps`,
so Lite and the deal page never disagree.
"""
import logging
import time as _time
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.lite.models import HeldAction, HeldActionChannel, HeldActionStatus

logger = logging.getLogger(__name__)

HOLD_SECONDS = 10
KINDS = ("bid", "counter", "accept", "reject")
OPEN = ("SENT", "COUNTERED")


def _utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _bad(detail: str, code: int = status.HTTP_400_BAD_REQUEST) -> HTTPException:
    return HTTPException(status_code=code, detail=detail)


# ── Holding ───────────────────────────────────────────────────────────────────


async def _club_for(db: AsyncSession, user):
    from app.clubs import service as clubs_service

    club = await clubs_service.get_club_for_user(db, user.id)
    if club is None:
        raise _bad("Lite actions are for club members", status.HTTP_403_FORBIDDEN)
    return club


async def _load_offer(db: AsyncSession, offer_id) -> object:
    from app.offers import service as offers_service

    try:
        oid = uuid.UUID(str(offer_id))
    except (TypeError, ValueError):
        raise _bad("Unknown offer")
    offer = await offers_service.get_offer_by_id(db, oid)
    if offer is None:
        raise _bad("This offer no longer exists", status.HTTP_404_NOT_FOUND)
    return offer


async def _check(db: AsyncSession, user, club, kind: str, payload: dict) -> None:
    """The endpoint's rules for this action, without any of its side effects."""
    from app.ai.assist import check_offer_terms
    from app.clubs.capabilities import Capability, ensure_club_capability
    from app.deps import get_buyer_user
    from app.offers import service as offers_service
    from app.offers.models import OfferStatus

    await ensure_club_capability(db, user, Capability.MARKET_WRITE)

    if kind == "bid":
        from app.deals import service as deals_service
        from app.offers.schemas import OfferCreateRequest
        from app.transfer_window import service as window_service

        await get_buyer_user(current_user=user, db=db)
        try:
            body = OfferCreateRequest(**payload)
        except Exception as exc:
            raise _bad(f"These terms aren't complete: {exc}")
        if not user.is_superuser and not await window_service.is_transfer_allowed(db):
            raise _bad("The transfer window is closed, so offers can't be made now.", status.HTTP_403_FORBIDDEN)
        if await offers_service.get_active_offer_for_buyer(db, body.player_id, club.id):
            raise _bad("You already have an open offer for this player.", status.HTTP_409_CONFLICT)
        active = await deals_service.get_active_deal_for_player(db, body.player_id)
        if active and getattr(active.status, "value", active.status) == "IN_PROGRESS":
            raise _bad("This player already has a transfer in progress.", status.HTTP_409_CONFLICT)
        try:
            await offers_service.check_new_offer(
                db, player_id=body.player_id, deal_type=body.deal_type, fee_amount=body.fee_amount,
                wage_weekly=body.wage_weekly, loan_start=body.loan_start, loan_end=body.loan_end,
                loan_fee=body.loan_fee, wage_split_pct=body.wage_split_pct, option_to_buy=body.option_to_buy,
                obligation_to_buy=body.obligation_to_buy, recall_allowed=body.recall_allowed,
                no_fee_reason=body.no_fee_reason, obligation_conditions=body.obligation_conditions,
                sale_id=body.sale_id, instalments=body.instalments, clauses=body.clauses, sell_on_pct=body.sell_on_pct,
            )
        except ValueError as exc:
            raise _bad(str(exc))
        terms = body.model_dump(mode="json", exclude_none=True)
        check = await check_offer_terms(db, viewer_club_id=club.id, terms=terms, user=user, club=club)
        money = check["money"]
        if money.get("over_budget") and not money.get("requires_approval"):
            raise _bad("This is more than your budget allows.")
        return

    offer = await _load_offer(db, payload.get("offer_id"))
    try:
        offers_service._require_party(offer, club.id)
    except ValueError as exc:
        raise _bad(str(exc), status.HTTP_403_FORBIDDEN)
    if offer.status not in (OfferStatus.SENT, OfferStatus.COUNTERED):
        raise _bad(f"This offer has already been {offer.status.value.lower()}.", status.HTTP_409_CONFLICT)
    try:
        offers_service._require_turn(offer, club.id)
    except ValueError as exc:
        raise _bad(str(exc), status.HTTP_409_CONFLICT)
    if kind == "counter":
        fee = payload.get("fee_amount")
        try:
            fee_value = Decimal(str(fee))
        except Exception:
            raise _bad("Give the fee you want to counter with.")
        if fee_value <= 0:
            raise _bad("Give the fee you want to counter with.")
    if kind in ("counter", "accept") and offer.from_club_id == club.id:
        terms = {"fee_amount": payload.get("fee_amount")} if kind == "counter" else {}
        check = await check_offer_terms(db, viewer_club_id=club.id, terms=terms, offer=offer, user=user, club=club)
        money = check["money"]
        if money.get("over_budget") and not money.get("requires_approval"):
            raise _bad("This is more than your budget allows.")


async def hold(db: AsyncSession, user, *, kind: str, payload: dict, ai_assisted: bool,
               channel: HeldActionChannel = HeldActionChannel.APP) -> HeldAction:
    """Check the action now and hold it for HOLD_SECONDS. Nothing is sent."""
    from app.audit import service as audit_service

    if kind not in KINDS:
        raise _bad(f"Unknown action: {kind}")
    club = await _club_for(db, user)
    await _check(db, user, club, kind, payload)
    action = HeldAction(
        user_id=user.id, club_id=club.id, kind=kind, payload_json=payload, ai_assisted=ai_assisted,
        status=HeldActionStatus.HELD, channel=channel,
        execute_at=datetime.now(timezone.utc) + timedelta(seconds=HOLD_SECONDS),
    )
    db.add(action)
    await db.flush()
    await audit_service.emit(
        db, entity_type="held_action", entity_id=action.id, action="held_action.held", actor_user_id=user.id,
        payload={"kind": kind, "payload": payload, "ai_assisted": ai_assisted},
        description=f"Confirmed a {kind} in Lite; sending in {HOLD_SECONDS} seconds",
    )
    return action


async def undo(db: AsyncSession, user, action_id: uuid.UUID) -> HeldAction:
    """Cancel a held action. 409 once it has been sent (or failed)."""
    from app.audit import service as audit_service

    action = (await db.execute(
        select(HeldAction).where(HeldAction.id == action_id).with_for_update()
    )).scalar_one_or_none()
    if action is None or action.user_id != user.id:
        raise _bad("Not found", status.HTTP_404_NOT_FOUND)
    if action.status != HeldActionStatus.HELD:
        raise _bad("Too late to undo: it has already been sent.", status.HTTP_409_CONFLICT)
    action.status = HeldActionStatus.CANCELLED
    await audit_service.emit(
        db, entity_type="held_action", entity_id=action.id, action="held_action.cancelled", actor_user_id=user.id,
        payload={"kind": action.kind}, description=f"Undid a {action.kind} before it was sent",
    )
    await db.flush()
    return action


# ── Executing ─────────────────────────────────────────────────────────────────


async def _run(db: AsyncSession, action: HeldAction, user) -> dict:
    """Do the action as `user`, through the same offer actions the endpoints
    use (offers/actions.py). The endpoints' permission dependencies don't
    apply here, so they are checked first."""
    from app.clubs import service as clubs_service
    from app.clubs.capabilities import Capability, ensure_club_capability
    from app.deps import get_buyer_user
    from app.offers import actions
    from app.offers import service as offers_service
    from app.offers.schemas import OfferCounterRequest, OfferCreateRequest

    await ensure_club_capability(db, user, Capability.MARKET_WRITE)
    club = await clubs_service.get_club_for_user(db, user.id)
    if club is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No club profile")
    p = action.payload_json
    try:
        if action.kind == "bid":
            await get_buyer_user(current_user=user, db=db)
            result = await actions.create_offer(db, user, club, OfferCreateRequest(**p, ai_assisted=action.ai_assisted))
            if result.approval is not None:
                return {"approval_id": str(result.approval.id)}
            return {"offer_id": str(result.offer.id)}
        offer_id = uuid.UUID(str(p["offer_id"]))
        offer = await offers_service.get_offer_by_id(db, offer_id)
        if offer is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Offer not found")
        if action.kind == "counter":
            body = OfferCounterRequest(fee_amount=Decimal(str(p["fee_amount"])),
                                       **({"ai_assisted": True, "ai_feature": "ask_proposal"} if action.ai_assisted else {}))
            await actions.counter_offer(db, user, club, offer, body)
            return {"offer_id": str(offer_id)}
        if action.kind == "accept":
            result = await actions.accept_offer(db, user, club, offer, ai_assisted=action.ai_assisted)
            if result.approval is not None:
                return {"offer_id": str(offer_id), "approval_id": str(result.approval.id)}
            return {"offer_id": str(offer_id), "deal_id": str(result.deal.id)}
        await actions.reject_offer(db, user, club, offer, ai_assisted=action.ai_assisted)
        return {"offer_id": str(offer_id)}
    except actions.OfferActionError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


async def execute_one(db: AsyncSession, action_id: uuid.UUID, now: datetime) -> HeldActionStatus | None:
    """Send one due action. Locked with SKIP LOCKED, so an undo racing it
    waits and then finds it sent; marked EXECUTED in the same transaction
    the endpoint commits, so the two can't disagree."""
    from app.audit import service as audit_service
    from app.auth.models import User

    action = (await db.execute(
        select(HeldAction).where(HeldAction.id == action_id, HeldAction.status == HeldActionStatus.HELD,
                                 HeldAction.execute_at <= now)
        .with_for_update(skip_locked=True)
    )).scalar_one_or_none()
    if action is None:
        return None
    user = await db.get(User, action.user_id)
    action.status = HeldActionStatus.EXECUTED
    action.executed_at = now
    await db.flush()
    try:
        if user is None or not user.is_active:
            raise _bad("The account that confirmed this is no longer active.", status.HTTP_403_FORBIDDEN)
        result = await _run(db, action, user)  # the endpoint commits, with the status above
    except HTTPException as exc:
        await db.rollback()
        detail = exc.detail if isinstance(exc.detail, str) else (exc.detail or {}).get("message", "It couldn't be sent.")
        return await _fail(db, action_id, now, detail)
    except Exception as exc:  # never leave an action stuck HELD
        logger.exception("Held action %s failed", action_id)
        await db.rollback()
        return await _fail(db, action_id, now, "Something went wrong sending it. Nothing was sent.")
    # Re-read after the endpoint's commit (populate_existing: nothing stale).
    action = (await db.execute(
        select(HeldAction).where(HeldAction.id == action_id).execution_options(populate_existing=True)
    )).scalar_one()
    action.result_json = result
    await audit_service.emit(
        db, entity_type="held_action", entity_id=action.id, action="held_action.executed",
        actor_user_id=action.user_id, payload={"kind": action.kind, "result": result},
        description=f"Sent a {action.kind} confirmed in Lite",
    )
    await db.commit()
    return HeldActionStatus.EXECUTED


async def _fail(db: AsyncSession, action_id: uuid.UUID, now: datetime, detail: str) -> HeldActionStatus:
    from app.audit import service as audit_service

    action = (await db.execute(
        select(HeldAction).where(HeldAction.id == action_id).execution_options(populate_existing=True)
    )).scalar_one()
    action.status = HeldActionStatus.FAILED
    action.executed_at = now
    action.error = str(detail)[:500]
    await audit_service.emit(
        db, entity_type="held_action", entity_id=action.id, action="held_action.failed",
        actor_user_id=action.user_id, payload={"kind": action.kind, "error": action.error},
        description=f"A {action.kind} confirmed in Lite couldn't be sent: {action.error}",
    )
    await db.commit()
    return HeldActionStatus.FAILED


async def due_ids(db: AsyncSession, now: datetime) -> list[uuid.UUID]:
    return list((await db.execute(
        select(HeldAction.id).where(HeldAction.status == HeldActionStatus.HELD, HeldAction.execute_at <= now)
        .order_by(HeldAction.execute_at).limit(50)
    )).scalars())


# ── Progress ──────────────────────────────────────────────────────────────────

_reply_cache: dict = {}
MIN_REPLY_SAMPLES = 20


async def typical_reply(db: AsyncSession) -> str | None:
    """'Clubs usually reply in 1 to 2 days': the platform's median time from
    an offer being sent to the other club's first answer. None with fewer
    than 20 answers to go on. Cached for an hour."""
    from app.offers.models import Offer, OfferEvent, OfferEventType

    hit = _reply_cache.get("v")
    if hit and hit[0] > _time.monotonic():
        return hit[1]
    rows = (await db.execute(
        select(Offer.created_at, OfferEvent.created_at)
        .join(OfferEvent, OfferEvent.offer_id == Offer.id)
        .where(OfferEvent.event_type.in_([OfferEventType.COUNTERED, OfferEventType.ACCEPTED, OfferEventType.REJECTED]))
        .order_by(OfferEvent.created_at)
    )).all()
    first: dict = {}
    for sent, answered in rows:
        first.setdefault(sent, answered)  # the first answer per offer
    waits = sorted((_utc(a) - _utc(s)).total_seconds() for s, a in first.items() if a and s)
    text = None
    if len(waits) >= MIN_REPLY_SAMPLES:
        median_h = waits[len(waits) // 2] / 3600
        if median_h < 2:
            text = "Clubs usually reply within a couple of hours."
        elif median_h < 24:
            text = "Clubs usually reply within a day."
        else:
            days = round(median_h / 24)
            text = f"Clubs usually reply in {max(1, days)} to {max(2, days + 1)} days."
    _reply_cache["v"] = (_time.monotonic() + 3600, text)
    return text


def _m(v) -> str:
    from app.notifications.copy import money

    return money(v) if v is not None else "an undisclosed fee"


async def _deal_steps_hint(db: AsyncSession, deal, club_id) -> str | None:
    from app.ai.assist import deal_steps
    from app.players.service import player_has_account

    steps = deal_steps(deal, club_id, await player_has_account(db, deal.player_id))
    return steps[0]["label"] if steps else None


async def progress(db: AsyncSession, action: HeldAction, now: datetime) -> dict:
    """The Sent screen: a title, a subline and five plain steps
    ({label, state: done|current|future|ended, hint})."""
    from app.approvals.models import PendingApproval
    from app.common.masking import buyer_name
    from app.deals import service as deals_service
    from app.deals.models import DealStage, DealStatus
    from app.offers import service as offers_service
    from app.players.models import Player

    p = action.payload_json or {}
    result = action.result_json or {}
    club_id = action.club_id
    offer = None
    oid = result.get("offer_id") or p.get("offer_id")
    if oid:
        offer = await offers_service.get_offer_by_id(db, uuid.UUID(str(oid)))
    player_id = (offer.player_id if offer else None) or p.get("player_id")
    player = (await db.execute(select(Player.name).where(Player.id == uuid.UUID(str(player_id))))).scalar_one_or_none() \
        if player_id else None
    player = player or "the player"

    # The other club, as this club may name it.
    other = "the other club"
    if offer is not None:
        if offer.from_club_id == club_id:
            other = offer.to_club.name if offer.to_club else "the seller"
        else:
            other = buyer_name(offer, offer.from_club, club_id, capitalise=False)
    elif p.get("to_club_id"):
        from app.clubs.models import Club

        other = (await db.execute(select(Club.name).where(Club.id == uuid.UUID(str(p["to_club_id"]))))).scalar_one_or_none() or other
    Other = other[:1].upper() + other[1:]

    kind = action.kind
    fee = p.get("fee_amount") if kind in ("bid", "counter") else (offer.fee_amount if offer else None)
    sent_label = {"bid": "Bid sent", "counter": "Counter sent", "accept": "Accepted", "reject": "Turned down"}[kind]
    title = {
        "bid": f"Bid sent to {Other}", "counter": f"Counter sent to {Other}",
        "accept": f"You accepted {_m(fee)}", "reject": f"You turned down {Other}",
    }[kind]
    subline = {
        "bid": f"{_m(fee)} for {player}.", "counter": f"You asked for {_m(fee)} for {player}.",
        "accept": f"{player}, with {other}.", "reject": f"Their offer for {player}.",
    }[kind]

    steps = [{"label": "You approved it", "state": "done", "hint": None}]
    seconds_left = None

    if action.status == HeldActionStatus.HELD:
        seconds_left = max(0, int(((_utc(action.execute_at) - now).total_seconds()) + 0.999))
        steps.append({"label": sent_label, "state": "current", "hint": f"Sending in {seconds_left} seconds"})
        future = (["They've been told"] if kind == "reject"
                  else (["Medical and personal terms", "Paperwork", "Signed"] if kind == "accept"
                        else [f"Waiting for {other} to reply", "Medical and personal terms", "Signed"]))
        steps += [{"label": f, "state": "future", "hint": None} for f in future]
        return {"title": title, "subline": subline, "steps": steps, "seconds_left": seconds_left}

    if action.status == HeldActionStatus.CANCELLED:
        return {"title": "Cancelled", "subline": "Nothing was sent.", "seconds_left": None,
                "steps": [{"label": "Cancelled. Nothing was sent.", "state": "ended", "hint": None}]}
    if action.status == HeldActionStatus.FAILED:
        return {"title": "Not sent", "subline": action.error or "It couldn't be sent.", "seconds_left": None,
                "steps": steps + [{"label": f"Not sent: {action.error or 'it was refused'}", "state": "ended", "hint": None}]}

    # Waiting for an approval?
    if result.get("approval_id"):
        approval = await db.get(PendingApproval, uuid.UUID(str(result["approval_id"])))
        state = getattr(getattr(approval, "status", None), "value", None)
        if state == "PENDING":
            steps.append({"label": "Waiting for your owner or sporting director to approve", "state": "current",
                          "hint": "They've been told. You'll hear when they decide."})
            steps += [{"label": f, "state": "future", "hint": None}
                      for f in ([f"Waiting for {other} to reply", "Signed"] if kind == "bid" else ["Signed"])]
            return {"title": "Sent for approval", "subline": subline, "steps": steps, "seconds_left": None}
        if state and state != "APPROVED_EXECUTED":
            steps.append({"label": f"Approval {state.replace('_', ' ').lower()}", "state": "ended", "hint": None})
            return {"title": "Not approved", "subline": subline, "steps": steps, "seconds_left": None}
        steps.append({"label": "Approved", "state": "done", "hint": None})

    if kind == "reject":
        steps += [{"label": "Turned down", "state": "done", "hint": None},
                  {"label": "They've been told", "state": "done", "hint": None}]
        return {"title": title, "subline": subline, "steps": steps, "seconds_left": None}

    steps.append({"label": sent_label, "state": "done", "hint": None})
    deal = None
    if offer is not None and offer.status.value == "ACCEPTED":
        from app.deals.models import Deal

        deal_id = (await db.execute(select(Deal.id).where(Deal.offer_id == offer.id))).scalars().first()
        deal = await deals_service.get_deal_by_id(db, deal_id) if deal_id else None

    if deal is None and offer is not None:
        st = offer.status.value
        if st in OPEN:
            if offer.last_actor_club_id == club_id:
                steps.append({"label": f"Waiting for {other} to reply", "state": "current", "hint": await typical_reply(db)})
            else:
                steps.append({"label": f"{Other} replied with {_m(offer.fee_amount)}, your turn", "state": "current",
                              "hint": "Open the offer to answer."})
            steps += [{"label": f, "state": "future", "hint": None} for f in ("Medical and personal terms", "Signed")]
        else:
            reason = {"REJECTED": "turned down", "WITHDRAWN": "withdrawn", "EXPIRED": "expired"}.get(st, st.lower())
            steps.append({"label": f"Deal ended: the offer was {reason}", "state": "ended", "hint": None})
        return {"title": title, "subline": subline, "steps": steps, "seconds_left": None}

    if deal is not None:
        stage, dstatus = deal.stage, deal.status
        hint = await _deal_steps_hint(db, deal, club_id)
        if dstatus not in (DealStatus.IN_PROGRESS, DealStatus.PENDING_COMPLETION, DealStatus.COMPLETED):
            steps.append({"label": "Fee agreed", "state": "done", "hint": None})
            steps.append({"label": f"Deal ended: {dstatus.value.replace('_', ' ').lower()}", "state": "ended", "hint": None})
            return {"title": title, "subline": subline, "steps": steps, "seconds_left": None, "deal_id": str(deal.id)}
        terms_stages = (DealStage.AGENT_NEGOTIATION, DealStage.PERSONAL_TERMS)
        paper_stages = (DealStage.PAPERWORK, DealStage.CONFIRMED)
        labels = ["Fee agreed", "Medical and personal terms", "Paperwork", "Signed"]
        current = {DealStage.AGREEMENT: 0, **{s: 1 for s in terms_stages}, **{s: 2 for s in paper_stages},
                   DealStage.COMPLETED: 99}[stage]
        if dstatus == DealStatus.COMPLETED:
            current = 99
        for i, label in enumerate(labels):
            state = "done" if (i < current or current == 99) else ("current" if i == current else "future")
            steps.append({"label": label, "state": state, "hint": hint if state == "current" else None})
        return {"title": title, "subline": subline, "steps": steps, "seconds_left": None, "deal_id": str(deal.id)}

    return {"title": title, "subline": subline, "steps": steps, "seconds_left": None}


async def deal_progress(db: AsyncSession, deal, club_id) -> dict:
    """The same steps for a deal on its own (GET /lite/deals/{id}/progress)."""
    from app.deals.models import DealStage, DealStatus

    hint = await _deal_steps_hint(db, deal, club_id)
    labels = ["Fee agreed", "Medical and personal terms", "Paperwork", "Signed"]
    current = {DealStage.AGREEMENT: 0, DealStage.AGENT_NEGOTIATION: 1, DealStage.PERSONAL_TERMS: 1,
               DealStage.PAPERWORK: 2, DealStage.CONFIRMED: 2, DealStage.COMPLETED: 99}[deal.stage]
    if deal.status == DealStatus.COMPLETED:
        current = 99
    ended = deal.status not in (DealStatus.IN_PROGRESS, DealStatus.PENDING_COMPLETION, DealStatus.COMPLETED)
    steps = []
    for i, label in enumerate(labels):
        state = "done" if (i < current or current == 99) else ("current" if i == current else "future")
        steps.append({"label": label, "state": state, "hint": hint if state == "current" else None})
    if ended:
        steps = steps[:max(1, current)] + [{"label": f"Deal ended: {deal.status.value.replace('_', ' ').lower()}",
                                            "state": "ended", "hint": None}]
    return {"steps": steps}
