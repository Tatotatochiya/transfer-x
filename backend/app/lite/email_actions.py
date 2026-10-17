"""Lite L8: decisions from email (lite-mode BACKEND §7).

An email about an offer waiting on the recipient carries up to three
buttons: "Ask for £21m", "Accept £18m", "Say no". Each links to
/lite/confirm/{token}?action=…, a minimal page showing the action card with
one Confirm button.

- Opening the link (GET) changes nothing: mail scanners follow links.
- Confirming (POST) holds the action for the usual 10 seconds with
  channel=EMAIL, so it can be undone like any Lite send.
- Every decision (accept, counter, and since 2026-10-17 saying no) needs
  the token's user signed in, and so does undoing it: turning down an offer
  ends a negotiation the other club is told about, and the link may have
  been forwarded. Mail scanners can't act either way: only a POST does.
- One token per email, used once, for 24 hours. If the offer has changed
  since the email went out, confirming is refused (409) with the new state.
- The card is the same one Lite shows, so an anonymous buyer stays masked.
  Its confidential parts (the club's own valuation of the player, and the
  counter TransferX suggests from it) go only to the recipient, signed in.
  Anyone else with the link (it may have been forwarded) sees what the email
  itself showed: the player, the other club, the offer and the time left.
  That holds for a used or expired link too.
"""
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.service import _hash_token
from app.config import settings
from app.lite.models import ActionToken, HeldActionChannel

TOKEN_HOURS = 24
def _require_recipient(token: ActionToken, current_user) -> None:
    if current_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sign in to confirm this.")
    if current_user.id != token.user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This link was sent to someone else.")
# What the confirm page may show someone who isn't the signed-in recipient.
PUBLIC_CARD = ("offer_id", "status", "player_name", "other_club", "deal_type", "fee", "expires_at")
LABELS = {"counter": "Ask for {amount}", "accept": "Accept {amount}", "reject": "Say no"}


def _money(v) -> str:
    n = float(v)
    if n >= 1e6:
        m = round(n / 1e6, 1)
        return f"£{int(m) if m == int(m) else m}m"
    return f"£{round(n / 1e3)}k"


def _version(offer) -> str:
    """Changes whenever the offer does: its status, its terms, or its last
    action. Terms count too, because two changes inside one clock tick
    would leave last_action_at the same."""
    import hashlib

    t = offer.last_action_at
    t = (t if t.tzinfo else t.replace(tzinfo=timezone.utc)).isoformat() if t else ""
    parts = [offer.status.value, str(offer.fee_amount), str(offer.loan_fee), str(offer.wage_weekly), t]
    return hashlib.sha1("|".join(parts).encode()).hexdigest()


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


async def offer_buttons(db: AsyncSession, user, offer_id: uuid.UUID) -> list[tuple[str, str]]:
    """(label, url) for an email about this offer, or [] when it isn't the
    recipient's move. Issues one token, valid for TOKEN_HOURS. Caller commits."""
    from app.lite import service as lite_service
    from app.offers.models import Offer

    try:
        card = await lite_service.offer_card(db, user, offer_id=offer_id)
    except Exception:
        return []
    if not card.get("your_move") or card.get("disabled_reason"):
        return []
    offer = await db.get(Offer, offer_id)
    allowed, buttons = [], []
    suggestion = card.get("counter_suggestion")
    if card.get("deal_type") == "PERMANENT" and suggestion:
        allowed.append("counter")
        buttons.append(("counter", suggestion))
    if card.get("fee") is not None:
        allowed.append("accept")
        buttons.append(("accept", card["fee"]))
    allowed.append("reject")
    buttons.append(("reject", None))

    raw = secrets.token_urlsafe(32)
    db.add(ActionToken(
        token_hash=_hash_token(raw), user_id=user.id, subject_kind="offer", subject_id=offer_id,
        allowed_actions=allowed, subject_version=_version(offer),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=TOKEN_HOURS),
    ))
    await db.flush()
    base = f"{settings.frontend_base_url}/lite/confirm/{raw}"
    out = []
    for action, amount in buttons:
        query = f"?action={action}" + (f"&amount={int(Decimal(str(amount)))}" if amount is not None else "")
        out.append((LABELS[action].format(amount=_money(amount) if amount is not None else ""), base + query))
    return out


async def _token(db: AsyncSession, raw: str, *, lock: bool = False) -> ActionToken:
    q = select(ActionToken).where(ActionToken.token_hash == _hash_token(raw))
    if lock:
        q = q.with_for_update()
    token = (await db.execute(q)).scalar_one_or_none()
    if token is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="This link isn't valid.")
    return token


async def view(db: AsyncSession, raw: str, action: str, amount: Decimal | None, current_user=None) -> dict:
    """What the confirm page shows. No side effects."""
    from app.auth.models import User
    from app.lite import service as lite_service
    from app.offers.models import Offer

    token = await _token(db, raw)
    user = await db.get(User, token.user_id)
    offer = await db.get(Offer, token.subject_id, populate_existing=True)  # its current version
    if user is None or not user.is_active or offer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="This link isn't valid.")
    state = "ready"
    if token.used_at is not None:
        state = "used"
    elif _aware(token.expires_at) < datetime.now(timezone.utc):
        state = "expired"
    elif _version(offer) != token.subject_version:
        state = "changed"
    if action not in token.allowed_actions:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="That isn't one of this email's choices.")
    card = await lite_service.offer_card(db, user, offer_id=offer.id)
    recipient = current_user is not None and current_user.id == user.id
    if action == "counter":
        # The amount in the link is the one the email showed. The card's own
        # suggestion can be the club's valuation, so it's for the recipient only.
        suggestion = card.get("counter_suggestion") if recipient else None
        amount = amount or (Decimal(str(suggestion)) if suggestion else None)
    elif action == "accept":
        amount = Decimal(str(card["fee"])) if card.get("fee") is not None else None
    else:
        amount = None
    return {
        "state": state,
        "action": action,
        "amount": float(amount) if amount is not None else None,
        "label": LABELS[action].format(amount=_money(amount) if amount is not None else ""),
        "needs_sign_in": True,  # every decision does (since 2026-10-17)
        # Whether whoever opened it is signed in as the recipient. Never the
        # recipient's address: the link may have been forwarded.
        "signed_in_as_recipient": recipient,
        "card": card if recipient else {k: card.get(k) for k in PUBLIC_CARD},
    }


async def confirm(db: AsyncSession, raw: str, action: str, amount: Decimal | None, current_user) -> dict:
    """Hold the action (channel EMAIL). Uses the token."""
    from app.auth.models import User
    from app.lite import held
    from app.offers.models import Offer

    token = await _token(db, raw, lock=True)
    if token.used_at is not None:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="This link has already been used.")
    if _aware(token.expires_at) < datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="This link has expired. Open TransferX to decide.")
    if action not in token.allowed_actions:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="That isn't one of this email's choices.")
    _require_recipient(token, current_user)
    offer = await db.get(Offer, token.subject_id, populate_existing=True)  # its current version
    if offer is None or _version(offer) != token.subject_version:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This has changed since we emailed you.")
    user = await db.get(User, token.user_id)

    payload: dict = {"offer_id": str(offer.id)}
    if action == "counter":
        if amount is None or amount <= 0:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Say how much to ask for.")
        payload["fee_amount"] = str(amount)
    action_row = await held.hold(db, user, kind=action, payload=payload, ai_assisted=False,
                                 channel=HeldActionChannel.EMAIL)
    token.used_at = datetime.now(timezone.utc)
    token.held_action_id = action_row.id
    await db.flush()
    return {"action_id": str(action_row.id), "execute_at": action_row.execute_at.isoformat()}


async def undo(db: AsyncSession, raw: str, current_user=None) -> None:
    """Undo the action this token confirmed, within its hold window. Only
    the recipient, signed in, as for confirming."""
    from app.auth.models import User
    from app.lite import held

    token = await _token(db, raw)
    _require_recipient(token, current_user)
    if token.held_action_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Nothing to undo.")
    user = await db.get(User, token.user_id)
    await held.undo(db, user, token.held_action_id)
