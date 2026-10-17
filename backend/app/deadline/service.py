"""Deadline-day mode (Q4 plan, Phase 2): every open transfer by what's left
to do before the window shuts, with what's blocking it and whose move it is.

It's a read model over the Transfers board (board.service), so masking,
"whose move" and what counts as open are exactly the board's. Each item
gets the next step and its owner from `assist.deal_steps` (the deal page's
own answer), a rough count of steps left, and two flags:

- `needs_you`: the next step is this club's (or either club's);
- `at_risk`: fewer hours left than HOURS_PER_STEP for each step still to
  do. A heuristic, said as such on screen: it flags what to chase, it
  doesn't predict.

`send_reminders` pushes each club once at 24, 6 and 2 hours before the
window closes, while it has transfers open.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

DEADLINE_MODE_HOURS = 72   # the screens switch to deadline mode inside this
HOURS_PER_STEP = 6         # less than this per step left flags a transfer at risk
REMINDER_HOURS = (24, 6, 2)
OPEN_COLUMNS = ("offers", "fee_agreed", "terms", "paperwork")
# Steps left after each column, before he's signed: agree the fee, personal
# terms, paperwork, signature.
STEPS_LEFT = {"offers": 4, "fee_agreed": 3, "terms": 2}


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


async def window_state(db: AsyncSession, now: datetime) -> dict:
    """The window as deadline mode sees it: open (with hours left), closed
    (with when the next opens) or none configured."""
    from app.transfer_window import service as window_service

    current = await window_service.get_current_window(db)
    if current is not None:
        closes = _aware(current.closes_at)
        hours = max(0.0, (closes - now).total_seconds() / 3600)
        return {"state": "open", "id": str(current.id), "name": current.name, "closes_at": closes.isoformat(),
                "hours_left": round(hours, 1), "deadline_mode": hours <= DEADLINE_MODE_HOURS}
    upcoming = await window_service.get_next_window(db)
    return {"state": "closed" if upcoming else "none", "id": None, "name": upcoming.name if upcoming else None,
            "closes_at": None, "opens_at": _aware(upcoming.opens_at).isoformat() if upcoming else None,
            "hours_left": None, "deadline_mode": False}


async def _deal_step(db: AsyncSession, deal_id: uuid.UUID, club_id: uuid.UUID) -> tuple[dict | None, int]:
    """The deal's next step ({label, owner}) and how many steps are left."""
    from app.ai.assist import deal_steps
    from app.deals import service as deals_service
    from app.deals.models import DealStage
    from app.players.service import player_has_account

    deal = await deals_service.get_deal_by_id(db, deal_id)
    if deal is None:
        return None, 1
    steps = deal_steps(deal, club_id, await player_has_account(db, deal.player_id))
    if deal.stage == DealStage.PAPERWORK:
        left = sum(1 for s in deals_service.paperwork_steps(deal) if not s["done"]) + 1
    elif deal.stage == DealStage.CONFIRMED:
        left = 1
    elif deal.stage == DealStage.AGREEMENT:
        left = 3
    else:
        left = 2
    return (steps[0] if steps else None), left


async def board(db: AsyncSession, club_id: uuid.UUID, now: datetime | None = None) -> dict:
    """Everything deadline mode shows for one club."""
    from app.board import service as board_service
    from app.common.schemas import WhoseMove

    now = now or datetime.now(timezone.utc)
    window = await window_state(db, now)
    hours = window["hours_left"]
    board_view = await board_service.get_board(db, club_id)

    items = []
    talking = 0
    for column in board_view.columns:
        if column.key == "talking":
            talking = len(column.cards)
        if column.key not in OPEN_COLUMNS:
            continue
        for card in column.cards:
            if card.kind == "deal":
                step, left = await _deal_step(db, card.entity_id, club_id)
            else:
                yours = card.whose_move == WhoseMove.YOUR
                step = {"label": "Answer the offer" if yours else f"Waiting for {card.counterparty or 'them'} to answer",
                        "owner": "you" if yours else "them"}
                left = STEPS_LEFT.get(card.column, 4)
            owner = (step or {}).get("owner")
            needs_you = card.whose_move == WhoseMove.YOUR or owner in ("you", "either")
            items.append({
                "kind": card.kind, "id": str(card.entity_id), "side": card.side,
                "player_id": str(card.player_id), "player_name": card.player_name,
                "player_photo_url": card.player_photo_url, "counterparty": card.counterparty,
                "amount": float(card.amount) if card.amount is not None else None,
                "stage": column.label, "detail": card.detail,
                "next_step": step, "steps_left": left,
                "needs_you": needs_you,
                "at_risk": hours is not None and hours < left * HOURS_PER_STEP,
                "link": card.link,
            })
    # What needs this club first, then what's at risk, then the most still to do.
    items.sort(key=lambda i: (not i["needs_you"], not i["at_risk"], -i["steps_left"], i["player_name"]))
    return {
        "window": window,
        "items": items,
        "counts": {"open": len(items), "needs_you": sum(i["needs_you"] for i in items),
                   "at_risk": sum(i["at_risk"] for i in items), "talking": talking},
        "hours_per_step": HOURS_PER_STEP,
    }


def _hours_text(hours: float) -> str:
    if hours < 1:
        return "less than an hour"
    h = int(hours)
    return f"{h} hour{'s' if h != 1 else ''}"


async def send_reminders(db: AsyncSession, now: datetime | None = None) -> int:
    """Push each club once at 24, 6 and 2 hours before the window closes,
    while it has transfers open. Returns how many clubs were told."""
    from app.clubs.models import Club
    from app.notifications import service as notif_service
    from app.notifications.models import NotificationType

    now = now or datetime.now(timezone.utc)
    window = await window_state(db, now)
    if window["state"] != "open":
        return 0
    hours = window["hours_left"]
    due = [t for t in REMINDER_HOURS if hours <= t]
    if not due:
        return 0
    threshold = min(due)  # the tightest one reached; the others went out earlier or are moot
    told = 0
    for club_id in (await db.execute(select(Club.id))).scalars():
        view = await board(db, club_id, now)
        counts = view["counts"]
        if not counts["open"]:
            continue
        n, mine = counts["open"], counts["needs_you"]
        message = (f"Deadline day: the window closes in {_hours_text(hours)}. "
                   f"{n} transfer{'s' if n != 1 else ''} still open"
                   + (f", {mine} waiting on you." if mine else ", none waiting on you."))
        await notif_service.notify_club(
            db, club_id, type=NotificationType.DEADLINE_DAY, message=message, link="/deadline",
            title="Deadline day", group_key=f"deadline:{window['id']}:{threshold}",
            deadline_at=datetime.fromisoformat(window["closes_at"]), once=True,
        )
        told += 1
    return told
