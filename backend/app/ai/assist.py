"""The workflow assistant: AI help at each step a club takes on TransferX.

Ground rules, in the order they are enforced here:

1. **The club sees what it may see, and so does the model.** Every fact passed
   to the model is built in this module from data the viewing club is already
   allowed to see on the page it is looking at: its own budget, never the
   other club's; the order book only for the selling club; an anonymous buyer
   stays "an undisclosed club".
2. **TransferX supplies the numbers.** Gaps against the fee model, budget
   headroom, deadlines, rule-based checks and guide prices are computed here.
   The model phrases and recommends, and any figure it suggests is checked
   against the facts before it reaches the page.
3. **It advises; the club acts.** Nothing here changes state. A suggestion is
   applied by the club through the normal, confirmed form, and that use is
   audited (`AI_SUGGESTION_USED`).
4. **Deterministic first.** The terms checker and the deal's next steps work
   with no model configured; the model only adds the narrative.
"""
from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Awaitable, Callable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.ai.client import chat
from app.ai.prompts import get_prompt
from app.config import settings

logger = logging.getLogger(__name__)

CURRENCY = "GBP"


def ai_available() -> bool:
    return any([settings.anthropic_api_key, settings.openai_api_key, settings.deepseek_api_key])


# ── Small helpers ──────────────────────────────────────────────────────────────


def _num(v) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _pct(a: float | None, b: float | None) -> float | None:
    """How far `a` is above (+) or below (−) `b`, in percent."""
    if a is None or not b:
        return None
    return round((a - b) / b * 100, 1)


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.rsplit("```", 1)[0].strip()
    return text


def _utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


# Results are cached under a key that includes the state they describe (an
# offer's last action, a deal's last update), so reopening a page costs no
# model call — and no rate-limit slot — until something actually changes.
_CACHE_TTL = 6 * 3600
_cache: dict[str, tuple[float, Any]] = {}


async def _cached(key: str, produce: Callable[[], Awaitable[Any]], ttl: int = _CACHE_TTL) -> tuple[Any, bool]:
    hit = _cache.get(key)
    if hit and time.monotonic() - hit[0] < ttl:
        return hit[1], True
    value = await produce()
    _cache[key] = (time.monotonic(), value)
    if len(_cache) > 2000:  # bounded: drop the oldest half
        for k in sorted(_cache, key=lambda k: _cache[k][0])[:1000]:
            _cache.pop(k, None)
    return value, False


async def _llm_json(prompt_key: str, *, user_id: uuid.UUID, endpoint: str, max_tokens: int = 900, **fmt) -> dict:
    """One model call returning a JSON object. Counts against the user's AI
    rate limit — call it only on a cache miss."""
    from app.ai.rate_limit import check_rate_limit

    check_rate_limit(user_id)
    messages = [
        {"role": "system", "content": get_prompt("SYSTEM_ADVISOR")},
        {"role": "user", "content": get_prompt(prompt_key).format(**fmt)},
    ]
    raw = await chat(messages, user_id=user_id, endpoint=endpoint, max_tokens=max_tokens, temperature=0.2)
    data = json.loads(_strip_fences(raw))
    if not isinstance(data, dict):
        raise ValueError("The assistant returned an unexpected answer")
    return data


def _dumps(facts: dict) -> str:
    return json.dumps(facts, indent=1, default=str)


def _strs(value, limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(v).strip() for v in value if str(v).strip()][:limit]


# ── Shared fact builders ───────────────────────────────────────────────────────


async def _player_facts(db: AsyncSession, player_id: uuid.UUID) -> dict:
    """Public facts about a player: profile, contract, the fee model."""
    from app.players.models import Contract, Player
    from app.valuation.service import get_latest_valuation

    player = (await db.execute(select(Player).where(Player.id == player_id))).scalar_one_or_none()
    if player is None:
        raise LookupError("Player not found")
    contract = (await db.execute(
        select(Contract).where(Contract.player_id == player_id, Contract.is_active.is_(True))
    )).scalars().first()
    valuation = await get_latest_valuation(db, player_id)
    contract_end = (contract.end_date if contract else None) or player.contract_expiry
    return {
        "name": player.name,
        "age": player.age,
        "position": player.position.value if player.position else None,
        "nationality": player.nationality,
        "contract_ends": contract_end.isoformat() if contract_end else None,
        "months_left_on_contract": (
            max(0, (contract_end.year - date.today().year) * 12 + contract_end.month - date.today().month)
            if contract_end else None
        ),
        "current_wage_weekly": _num(contract.wage_weekly) if contract else None,
        "fee_model": {
            "fair_value": _num(valuation.fair_value),
            "range_low": _num(valuation.fair_value_low),
            "range_high": _num(valuation.fair_value_high),
            "confidence": valuation.confidence.value if hasattr(valuation.confidence, "value") else str(valuation.confidence),
        } if valuation else None,
    }


async def _contract_ends(db: AsyncSession, players) -> dict:
    """Contract end per player: the active contract's end date, else the
    player record's (imported players carry one or the other)."""
    from app.players.models import Contract

    ids = [p.id for p in players]
    ends = {p.id: p.contract_expiry for p in players}
    if ids:
        rows = (await db.execute(
            select(Contract.player_id, Contract.end_date).where(Contract.player_id.in_(ids), Contract.is_active.is_(True))
        )).all()
        for pid, end in rows:
            if end is not None:
                ends[pid] = end
    return ends


async def _budget_facts(db: AsyncSession, club_id: uuid.UUID) -> dict | None:
    """The viewing club's own budget — never another club's."""
    from app.clubs.models import ClubFinance

    fin = (await db.execute(select(ClubFinance).where(ClubFinance.club_id == club_id))).scalar_one_or_none()
    if fin is None:
        return None
    return {
        "transfer_budget_remaining": _num(fin.transfer_remaining),
        "wage_budget_remaining_weekly": _num(fin.wage_remaining_weekly),
    }


# ── Phase 1a: offer terms checker (deterministic) ─────────────────────────────

# Senior professional contracts in the major leagues run at most five years.
_MAX_CONTRACT_YEARS = 5


def check_terms(terms: dict, *, role: str, player: dict, budget: dict | None,
                guide_price: float | None, current: dict | None = None) -> list[dict]:
    """Rule-based warnings on a set of offer terms, from the viewer's side.

    `terms` uses the offer's field names. `current` is the offer as it stands
    when checking a counter, so money already reserved is not counted twice.
    Each warning: {"severity": "high"|"medium"|"low", "code", "message"}.
    """
    out: list[dict] = []

    def warn(severity: str, code: str, message: str) -> None:
        out.append({"severity": severity, "code": code, "message": message})

    loan = terms.get("deal_type") == "LOAN"
    fee = _num(terms.get("loan_fee") if loan else terms.get("fee_amount"))
    wage = _num(terms.get("wage_weekly"))
    years = terms.get("contract_years")
    model = player.get("fee_model") or {}
    low, high = _num(model.get("range_low")), _num(model.get("range_high"))
    fmt = lambda v: f"£{v / 1e6:.1f}m" if v >= 1e6 else f"£{v / 1e3:.0f}k"  # noqa: E731

    # ── Price against the model and the guide ───────────────────────────────
    if not loan and fee is not None and fee > 0:
        if high and fee > high * 1.25:
            warn("medium" if role == "buyer" else "low", "above_model",
                 f"The fee is {_pct(fee, high):.0f}% above the top of the model's range ({fmt(high)}).")
        if low and fee < low * 0.75:
            warn("medium" if role == "seller" else "low", "below_model",
                 f"The fee is {abs(_pct(fee, low)):.0f}% below the bottom of the model's range ({fmt(low)}).")
        if guide_price and role == "seller" and fee < guide_price * 0.8:
            warn("low", "below_guide", f"The fee is {abs(_pct(fee, guide_price)):.0f}% below your guide price of {fmt(guide_price)}.")
    if not loan and fee == 0:
        warn("medium", "no_fee", "No transfer fee — only right for a player whose contract is about to end.")

    # ── Buyer's budget ──────────────────────────────────────────────────────
    if role == "buyer" and budget:
        already = _num((current or {}).get("fee_amount")) or 0 if current else 0
        room = budget.get("transfer_budget_remaining")
        if fee is not None and room is not None and fee - already > room:
            warn("high", "over_transfer_budget",
                 f"The fee is more than your remaining transfer budget of {fmt(room)}."
                 if not already else
                 f"Raising the fee needs {fmt(fee - already)} more, but only {fmt(room)} of your transfer budget is left.")
        wage_room = budget.get("wage_budget_remaining_weekly")
        already_wage = _num((current or {}).get("wage_weekly")) or 0 if current else 0
        pay = wage
        if loan and wage is not None and terms.get("wage_split_pct") is not None:
            pay = wage * float(terms["wage_split_pct"])
        if pay is not None and wage_room is not None and pay - already_wage > wage_room:
            warn("high", "over_wage_budget",
                 f"The weekly wage exceeds your remaining wage budget ({fmt(wage_room)}/wk).")

    # ── Wage and contract ───────────────────────────────────────────────────
    current_wage = player.get("current_wage_weekly")
    if not loan and wage is not None and current_wage and wage < current_wage * 0.9:
        warn("medium", "wage_below_current",
             f"The wage is below his current {fmt(current_wage)}/wk — personal terms may be hard to agree.")
    if years:
        if years > _MAX_CONTRACT_YEARS:
            warn("high", "contract_too_long", f"Contracts run at most {_MAX_CONTRACT_YEARS} years.")
        age = player.get("age")
        if age and age >= 31 and years >= 4:
            warn("medium", "long_contract_older_player", f"A {years}-year contract takes him past {age + years}.")

    # ── Payment structure ───────────────────────────────────────────────────
    instalments = terms.get("instalments") or []
    today = date.today()
    for row in instalments:
        try:
            due = date.fromisoformat(str(row.get("due_date")))
        except ValueError:
            continue
        if due < today:
            warn("high", "instalment_in_past", f"An instalment is due on {due.isoformat()}, which has passed.")
            break
    if instalments:
        try:
            last = max(date.fromisoformat(str(r.get("due_date"))) for r in instalments)
            if (last - today).days > 4 * 365:
                warn("medium", "long_instalments", "Instalments run beyond four years.")
        except ValueError:
            pass
    clause_total = sum(_num(c.get("amount")) or 0 for c in terms.get("clauses") or [])
    if fee and clause_total > fee * 0.5:
        warn("low", "heavy_add_ons", f"Add-ons total {fmt(clause_total)}, over half the fee.")
    sell_on = _num(terms.get("sell_on_pct"))
    if sell_on is not None and sell_on > 0.3:
        warn("medium", "high_sell_on", f"A {sell_on * 100:.0f}% sell-on is well above the usual 10–20%.")

    # ── Loans ───────────────────────────────────────────────────────────────
    if loan:
        contract_end = player.get("contract_ends")
        loan_end = terms.get("loan_end")
        if contract_end and loan_end and str(loan_end) > str(contract_end):
            warn("high", "loan_past_contract", "The loan runs past the end of his contract.")
        if terms.get("obligation_to_buy") and not (terms.get("obligation_conditions") or "").strip():
            warn("medium", "unconditional_obligation",
                 "The obligation to buy has no conditions, so it binds whatever happens during the loan.")
        option = _num(terms.get("option_to_buy"))
        if option and low and option < low * 0.75 and role == "seller":
            warn("medium", "option_below_model", f"The purchase option is well below the model's range ({fmt(low)}).")
        split = _num(terms.get("wage_split_pct"))
        if split is not None and split < 0.5 and role == "seller":
            warn("low", "low_wage_share", f"The borrowing club pays only {split * 100:.0f}% of his wage.")

    order = {"high": 0, "medium": 1, "low": 2}
    return sorted(out, key=lambda w: order[w["severity"]])


async def _guide_price(db: AsyncSession, player_id: uuid.UUID) -> float | None:
    """The open listing's asking price — public; auctions excluded."""
    from app.sales.models import Sale, SaleStatus, SaleType

    sale = (await db.execute(
        select(Sale).where(Sale.player_id == player_id, Sale.status == SaleStatus.OPEN, Sale.sale_type != SaleType.AUCTION)
    )).scalars().first()
    return _num(sale.asking_price) if sale else None


async def check_offer_terms(db: AsyncSession, *, viewer_club_id: uuid.UUID, terms: dict,
                            offer=None) -> dict:
    """Checks for a draft offer (no `offer`: the viewer is the buyer) or for a
    counter/incoming offer (`offer` given: the viewer's side comes from it)."""
    player_id = offer.player_id if offer is not None else uuid.UUID(str(terms["player_id"]))
    role = "buyer" if offer is None or offer.from_club_id == viewer_club_id else "seller"
    player = await _player_facts(db, player_id)
    budget = await _budget_facts(db, viewer_club_id) if role == "buyer" else None
    current = None
    if offer is not None:
        current = {"fee_amount": offer.fee_amount, "wage_weekly": offer.wage_weekly}
        merged = _offer_terms(offer)
        merged.update({k: v for k, v in terms.items() if v is not None})
        terms = merged
    return {
        "role": role,
        "warnings": check_terms(
            terms, role=role, player=player, budget=budget,
            guide_price=await _guide_price(db, player_id), current=current,
        ),
    }


# ── Phase 1b/1c: offer facts, advisor and negotiation summary ────────────────


def _offer_terms(offer) -> dict:
    return {
        "deal_type": offer.deal_type.value if hasattr(offer.deal_type, "value") else offer.deal_type,
        "fee_amount": _num(offer.fee_amount),
        "wage_weekly": _num(offer.wage_weekly),
        "contract_years": offer.contract_years,
        "instalments": offer.instalments or [],
        "clauses": offer.clauses or [],
        "sell_on_pct": _num(offer.sell_on_pct),
        "loan_start": offer.loan_start.isoformat() if offer.loan_start else None,
        "loan_end": offer.loan_end.isoformat() if offer.loan_end else None,
        "loan_fee": _num(offer.loan_fee),
        "wage_split_pct": _num(offer.wage_split_pct),
        "option_to_buy": _num(offer.option_to_buy),
        "obligation_to_buy": offer.obligation_to_buy,
        "obligation_conditions": offer.obligation_conditions,
        "recall_allowed": offer.recall_allowed,
    }


def _masked(offer, viewer_club_id: uuid.UUID) -> bool:
    """An anonymous buyer stays hidden from the seller until acceptance."""
    from app.offers.models import OfferStatus

    return bool(offer.is_anonymous) and viewer_club_id != offer.from_club_id and offer.status != OfferStatus.ACCEPTED


async def _load_offer(db: AsyncSession, offer_id: uuid.UUID, viewer_club_id: uuid.UUID):
    from app.offers.models import Offer

    offer = (await db.execute(
        select(Offer).where(Offer.id == offer_id).options(
            selectinload(Offer.events), selectinload(Offer.messages),
            selectinload(Offer.from_club), selectinload(Offer.to_club), selectinload(Offer.player),
        )
    )).scalar_one_or_none()
    if offer is None or viewer_club_id not in (offer.from_club_id, offer.to_club_id):
        raise LookupError("Offer not found")
    return offer


async def offer_facts(db: AsyncSession, offer, viewer_club_id: uuid.UUID) -> dict:
    from app.offers.models import OfferEventType, OfferStatus

    role = "buyer" if viewer_club_id == offer.from_club_id else "seller"
    player = await _player_facts(db, offer.player_id)
    guide = await _guide_price(db, offer.player_id)
    terms = _offer_terms(offer)
    loan = terms["deal_type"] == "LOAN"
    fee = terms["loan_fee"] if loan else terms["fee_amount"]
    model = player.get("fee_model") or {}

    your_turn = offer.status in (OfferStatus.SENT, OfferStatus.COUNTERED) and (
        offer.last_actor_club_id != viewer_club_id if offer.last_actor_club_id else role == "seller"
    )
    rounds = sum(1 for e in offer.events if e.event_type in (OfferEventType.COUNTERED, OfferEventType.IMPROVED))
    expires = _utc(offer.expires_at)

    facts: dict = {
        "currency": CURRENCY,
        "viewer_role": role,
        "status": offer.status.value,
        "your_turn": your_turn,
        "counter_rounds_so_far": rounds,
        "expires_in_days": round((expires - datetime.now(timezone.utc)).total_seconds() / 86400, 1) if expires else None,
        "other_club": ("an undisclosed club" if _masked(offer, viewer_club_id) else offer.from_club.name)
        if role == "seller" else (offer.to_club.name if offer.to_club else None),
        "player": player,
        "current_terms": terms,
        "listing_guide_price": guide,
        "fee_vs_model_pct": _pct(fee, _num(model.get("fair_value"))) if not loan else None,
        "fee_vs_guide_pct": _pct(fee, guide) if not loan else None,
    }
    if role == "buyer":
        facts["your_budget"] = await _budget_facts(db, viewer_club_id)
    else:
        # The seller already sees every competing offer in its order book.
        from app.offers.models import Offer

        rivals = (await db.execute(
            select(Offer).where(
                Offer.player_id == offer.player_id, Offer.id != offer.id,
                Offer.status.in_([OfferStatus.SENT, OfferStatus.COUNTERED]),
            )
        )).scalars().all()
        fees = [_num(o.fee_amount) for o in rivals if o.fee_amount is not None and o.deal_type == offer.deal_type]
        facts["competing_offers"] = {"count": len(rivals), "best_fee": max(fees) if fees else None}
    return facts


def _validate_suggestion(raw: dict | None, facts: dict) -> dict | None:
    """Keep only known keys with sane numbers, near the facts' own figures —
    the model may suggest, but not conjure a price from nowhere."""
    if not isinstance(raw, dict):
        return None
    terms = facts["current_terms"]
    model = (facts["player"].get("fee_model") or {})
    anchors = [v for v in (terms.get("fee_amount"), terms.get("loan_fee"), model.get("range_low"),
                           model.get("range_high"), facts.get("listing_guide_price")) if v]
    out: dict = {}
    for key in ("fee_amount", "wage_weekly", "contract_years", "sell_on_pct", "loan_fee", "wage_split_pct", "option_to_buy"):
        v = _num(raw.get(key))
        if v is None or v < 0:
            continue
        if key in ("sell_on_pct", "wage_split_pct") and v > 1:
            v = v / 100 if v <= 100 else None
            if v is None:
                continue
        if key == "contract_years":
            v = int(round(v))
            if not 1 <= v <= _MAX_CONTRACT_YEARS:
                continue
        if key in ("fee_amount", "loan_fee", "option_to_buy") and anchors:
            if not (min(anchors) * 0.5 <= v <= max(anchors) * 2):
                continue
        out[key] = v
    return out or None


async def offer_advice(db: AsyncSession, offer_id: uuid.UUID, *, viewer_club_id: uuid.UUID,
                       user_id: uuid.UUID, refresh: bool = False) -> dict:
    offer = await _load_offer(db, offer_id, viewer_club_id)
    facts = await offer_facts(db, offer, viewer_club_id)
    checks = check_terms(
        facts["current_terms"], role=facts["viewer_role"], player=facts["player"],
        budget=facts.get("your_budget"), guide_price=facts["listing_guide_price"],
    )
    key = f"advice:{offer.id}:{viewer_club_id}:{offer.last_action_at.isoformat()}"
    if refresh:
        _cache.pop(key, None)

    async def produce():
        data = await _llm_json(
            "OFFER_ADVICE_USER", user_id=user_id, endpoint="offer-advice",
            role=facts["viewer_role"], facts_json=_dumps(facts), checks_json=_dumps(checks),
        )
        rec = str(data.get("recommendation", "")).lower()
        if rec not in ("accept", "counter", "reject", "wait"):
            rec = "wait"
        if not facts["your_turn"]:
            rec = "wait"
        return {
            "summary": str(data.get("summary", "")).strip(),
            "recommendation": rec,
            "suggested_terms": _validate_suggestion(data.get("suggested_terms"), facts) if rec == "counter" else None,
            "reasons": _strs(data.get("reasons"), 4),
            "watch_outs": _strs(data.get("watch_outs"), 3),
        }

    result, cached = await _cached(key, produce)
    return {**result, "checks": checks, "facts": _public_offer_facts(facts), "cached": cached}


def _public_offer_facts(facts: dict) -> dict:
    """The handful of computed figures shown beside the advice."""
    model = facts["player"].get("fee_model") or {}
    return {
        "model_fair_value": model.get("fair_value"),
        "model_range": [model.get("range_low"), model.get("range_high")] if model else None,
        "fee_vs_model_pct": facts.get("fee_vs_model_pct"),
        "listing_guide_price": facts.get("listing_guide_price"),
        "competing_offers": facts.get("competing_offers"),
        "your_budget": facts.get("your_budget"),
    }


async def negotiation_summary(db: AsyncSession, offer_id: uuid.UUID, *, viewer_club_id: uuid.UUID,
                              user_id: uuid.UUID) -> dict:
    offer = await _load_offer(db, offer_id, viewer_club_id)
    role = "buyer" if viewer_club_id == offer.from_club_id else "seller"
    masked = _masked(offer, viewer_club_id)

    def who(club_id) -> str:
        if club_id is None:
            return "TransferX"
        return "you" if club_id == viewer_club_id else "them"

    history = []
    for e in sorted(offer.events, key=lambda e: e.created_at):
        if e.event_type.value == "MESSAGE":
            continue
        entry = {"when": e.created_at.date().isoformat(), "by": who(e.actor_club_id), "event": e.event_type.value}
        payload = e.payload or {}
        if payload.get("fee_amount"):
            entry["fee_amount"] = _num(payload["fee_amount"])
        if payload.get("changes"):
            entry["changes"] = payload["changes"]
        history.append(entry)
    messages = [
        {"when": m.created_at.date().isoformat(), "by": who(m.sender_club_id), "text": m.body[:400]}
        for m in sorted(offer.messages, key=lambda m: m.created_at)
    ][-12:]
    # Who moved on what, worked out here rather than inferred by the model:
    # each proposal's terms against the previous one.
    moves = {"you": [], "them": []}
    last_fee = None
    for h in history:
        fee = h.get("fee_amount")
        if h["event"] in ("SENT", "COUNTERED", "IMPROVED") and h["by"] in moves:
            changed = []
            if fee is not None and last_fee is not None and fee != last_fee:
                changed.append(f"fee {'up' if fee > last_fee else 'down'} from {last_fee:,.0f} to {fee:,.0f}")
            for k, v in (h.get("changes") or {}).items():
                if k != "fee_amount":
                    changed.append(f"{k} set to {v}")
            if changed:
                moves[h["by"]].append("; ".join(changed))
        if fee is not None:
            last_fee = fee
    facts = {
        "currency": CURRENCY,
        "viewer_role": role,
        "moves_by_you": moves["you"],
        "moves_by_them": moves["them"],
        "other_club": "an undisclosed club" if masked else (offer.from_club.name if role == "seller" else offer.to_club.name if offer.to_club else None),
        "player": offer.player.name if offer.player else None,
        "status": offer.status.value,
        "current_terms": _offer_terms(offer),
        "history": history,
        "messages": messages,
    }
    key = f"summary:{offer.id}:{viewer_club_id}:{offer.last_action_at.isoformat()}:{len(messages)}"

    async def produce():
        data = await _llm_json(
            "NEGOTIATION_SUMMARY_USER", user_id=user_id, endpoint="negotiation-summary",
            role=role, facts_json=_dumps(facts),
        )
        return {
            "summary": str(data.get("summary", "")).strip(),
            "gap": (str(data["gap"]).strip() or None) if data.get("gap") else None,
            "their_moves": _strs(data.get("their_moves"), 4),
            "your_moves": _strs(data.get("your_moves"), 4),
        }

    result, cached = await _cached(key, produce)
    return {**result, "rounds": sum(1 for h in history if h["event"] in ("COUNTERED", "IMPROVED")), "cached": cached}


# ── Phase 2a: deal next steps ─────────────────────────────────────────────────


def deal_steps(deal, viewer_club_id: uuid.UUID) -> list[dict]:
    """What the deal is waiting on, and who must act — worked out from the
    stage machine, not by the model. Owners: "you", "them", "either",
    "player", "agent", "staff"."""
    from app.deals.models import DealStage, DealStatus
    from app.deals.service import paperwork_steps

    if deal.status not in (DealStatus.IN_PROGRESS, DealStatus.PENDING_COMPLETION):
        return []
    side = "buyer" if viewer_club_id == deal.buyer_club_id else "seller"

    def owner_of(s: str) -> str:
        return "you" if s == side else "them"

    steps: list[dict] = []
    stage = deal.stage
    if stage == DealStage.AGREEMENT:
        steps.append({"label": "Move the deal on to personal terms", "owner": "either"})
    elif stage == DealStage.AGENT_NEGOTIATION:
        steps.append({"label": "Agree the agent's commission", "owner": owner_of("buyer")})
    elif stage == DealStage.PERSONAL_TERMS:
        pt = deal.personal_terms
        consent = (pt.player_consent.value if pt is not None and hasattr(pt.player_consent, "value")
                   else (pt.player_consent if pt is not None else None))
        if pt is None:
            steps.append({
                "label": "Propose personal terms to the player",
                "owner": "agent" if deal.commission_agent_id else owner_of("buyer"),
            })
        elif consent == "AGREED":
            steps.append({"label": "Advance to paperwork", "owner": "either"})
        else:
            steps.append({
                "label": "Get the player's answer on the proposed terms",
                "owner": "player" if getattr(pt, "agent_id", None) is None else "agent",
            })
    elif stage == DealStage.PAPERWORK:
        for s in paperwork_steps(deal):
            if not s["done"]:
                steps.append({"label": s["label"], "owner": owner_of(s["owner"])})
    elif stage == DealStage.CONFIRMED:
        sla = _utc(deal.sla_deadline)
        steps.append({
            "label": "Complete the transfer",
            "owner": "either",
            "due": sla.date().isoformat() if sla else None,
        })
    return steps


async def deal_next_steps(db: AsyncSession, deal_id: uuid.UUID, *, viewer_club_id: uuid.UUID,
                          user_id: uuid.UUID) -> dict:
    import hashlib

    from app.deals.service import get_deal_by_id

    deal = await get_deal_by_id(db, deal_id)
    if deal is None or viewer_club_id not in (deal.buyer_club_id, deal.seller_club_id):
        raise LookupError("Deal not found")
    steps = deal_steps(deal, viewer_club_id)
    role = "buyer" if viewer_club_id == deal.buyer_club_id else "seller"
    idle_days = (datetime.now(timezone.utc) - _utc(deal.updated_at)).days if deal.updated_at else None

    brief = None
    if steps and ai_available():
        other = deal.seller_club if role == "buyer" else deal.buyer_club
        facts = {
            "currency": CURRENCY,
            "viewer_role": role,
            "player": deal.player.name if deal.player else None,
            "other_club": other.name if other else None,
            "deal_type": deal.deal_type.value,
            "stage": deal.stage.value,
            "agreed_fee": _num(deal.agreed_fee),
            "days_since_last_movement": idle_days if idle_days and idle_days >= 3 else None,
            "outstanding_steps": steps,
            "window_or_sla_deadline": _utc(deal.sla_deadline).date().isoformat() if deal.sla_deadline else None,
        }
        fingerprint = hashlib.sha1(_dumps(facts).encode()).hexdigest()[:12]
        try:
            brief, _ = await _cached(
                f"deal:{deal.id}:{viewer_club_id}:{fingerprint}",
                lambda: _deal_brief(facts, role, user_id),
            )
        except Exception as exc:  # the steps stand on their own
            logger.warning("Deal brief unavailable: %s", exc)
    return {"steps": steps, "idle_days": idle_days, "brief": brief}


async def _deal_brief(facts: dict, role: str, user_id: uuid.UUID) -> dict:
    data = await _llm_json("DEAL_BRIEF_USER", user_id=user_id, endpoint="deal-brief", max_tokens=400,
                           role=role, facts_json=_dumps(facts))
    return {"headline": str(data.get("headline", "")).strip(), "advice": _strs(data.get("advice"), 3)}
