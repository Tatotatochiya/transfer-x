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
import re
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


async def _llm_json(prompt_key: str, *, user_id: uuid.UUID, endpoint: str, max_tokens: int = 900,
                    bucket: str = "default", **fmt) -> dict:
    """One model call returning a JSON object. Counts against the user's AI
    rate limit (`bucket`: Ask has its own) — call it only on a cache miss."""
    from app.ai.rate_limit import check_rate_limit

    check_rate_limit(user_id, bucket)
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


async def _player_facts(db: AsyncSession, player_id: uuid.UUID, viewer_club_id: uuid.UUID | None = None) -> dict:
    """Public facts about a player, for any club's assistant. His wage is the
    contract wage only for the club holding the contract; any other club gets
    the public estimate, flagged as one (a rival's contract is confidential)."""
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
        **({"current_wage_weekly": _num(contract.wage_weekly), "current_wage_is_estimate": False}
           if contract is not None and contract.club_id == viewer_club_id else
           {"current_wage_weekly": _num(player.wage_weekly), "current_wage_is_estimate": True}),
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
        "transfer_budget_total": _num(fin.transfer_budget_total),
    }


# ── Money effect (shared by check_terms and Lite's money panel) ──────────────


def money_effect(terms: dict, *, role: str, budget: dict | None, reserved: dict | None = None) -> dict:
    """What an offer's terms do to the viewing club's money.

    A buyer's figures use `offers.service._reservation`, the arithmetic the
    offer paths reserve with (fee or loan fee, add-ons, the loan wage split),
    less what the offer already holds (`reserved`, when countering or
    accepting), and "over" is exactly the test `reserve_budget` refuses on.
    So the budget warnings and Lite's money panel agree with the refusal.
    A seller's fee arrives when the deal completes; there is no wage line.
    """
    from app.deals.models import DealType
    from app.offers.service import _reservation

    def dec(v):
        return Decimal(str(v)) if v is not None else None

    loan = terms.get("deal_type") == "LOAN"
    transfer, wage = _reservation(
        deal_type=DealType.LOAN if loan else DealType.PERMANENT,
        fee_amount=dec(terms.get("fee_amount")),
        loan_fee=dec(terms.get("loan_fee")),
        add_ons=terms.get("add_ons") or None,
        wage_weekly=dec(terms.get("wage_weekly")),
        wage_split_pct=dec(terms.get("wage_split_pct")),
        clauses=terms.get("clauses") or None,
    )
    budget = budget or {}
    before = budget.get("transfer_budget_remaining")
    wage_before = budget.get("wage_budget_remaining_weekly")
    out = {
        "transfer_budget": budget.get("transfer_budget_total"),
        "transfer_before": before,
        "on_completion": role == "seller",
    }
    if role == "seller":
        incoming = float(dec(terms.get("loan_fee") if loan else terms.get("fee_amount")) or 0)
        out.update({
            "this_action": incoming,
            "transfer_after": before + incoming if before is not None else None,
            "wage_before_weekly": None, "wage_after_weekly": None, "wage_this_action": None,
            "over_transfer": False, "over_wage": False, "over_budget": False,
        })
        return out
    reserved = reserved or {}
    this = float(transfer) - float(reserved.get("transfer") or 0)
    this_wage = float(wage) - float(reserved.get("wage") or 0)
    over_transfer = before is not None and this > before
    over_wage = wage_before is not None and this_wage > wage_before
    out.update({
        "this_action": this,
        "transfer_after": before - this if before is not None else None,
        "wage_this_action": this_wage,
        "wage_before_weekly": wage_before,
        "wage_after_weekly": wage_before - this_wage if wage_before is not None else None,
        "over_transfer": over_transfer, "over_wage": over_wage,
        "over_budget": over_transfer or over_wage,
    })
    return out


# ── Phase 1a: offer terms checker (deterministic) ─────────────────────────────

# Senior professional contracts in the major leagues run at most five years.
_MAX_CONTRACT_YEARS = 5


def check_terms(terms: dict, *, role: str, player: dict, budget: dict | None,
                guide_price: float | None, current: dict | None = None) -> list[dict]:
    """Rule-based warnings on a set of offer terms, from the viewer's side.

    `terms` uses the offer's field names. `current` is what the offer already
    holds when checking a counter or an acceptance ({"transfer", "wage"}), so
    money already reserved is not counted twice.
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
        money = money_effect(terms, role=role, budget=budget, reserved=current)
        room = budget.get("transfer_budget_remaining")
        if money["over_transfer"]:
            warn("high", "over_transfer_budget",
                 f"The fee is more than your remaining transfer budget of {fmt(room)}."
                 if not (current or {}).get("transfer") else
                 f"Raising the fee needs {fmt(money['this_action'])} more, but only {fmt(room)} of your transfer budget is left.")
        if money["over_wage"]:
            warn("high", "over_wage_budget",
                 f"The weekly wage exceeds your remaining wage budget ({fmt(budget.get('wage_budget_remaining_weekly'))}/wk).")

    # ── Wage and contract ───────────────────────────────────────────────────
    current_wage = player.get("current_wage_weekly")
    if not loan and wage is not None and current_wage and wage < current_wage * 0.9:
        current = "estimated current" if player.get("current_wage_is_estimate") else "current"
        warn("medium", "wage_below_current",
             f"The wage is below his {current} {fmt(current_wage)}/wk — personal terms may be hard to agree.")
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
                            offer=None, user=None, club=None) -> dict:
    """Checks for a draft offer (no `offer`: the viewer is the buyer) or for a
    counter/incoming offer (`offer` given: the viewer's side comes from it).

    `money` is the effect on the viewer's budget (see `money_effect`); with
    `user` and `club`, it also says whether the spending-approval rule would
    capture the action, from the same rule the offer endpoints apply."""
    player_id = offer.player_id if offer is not None else uuid.UUID(str(terms["player_id"]))
    role = "buyer" if offer is None or offer.from_club_id == viewer_club_id else "seller"
    player = await _player_facts(db, player_id, viewer_club_id)
    own_budget = await _budget_facts(db, viewer_club_id)
    budget = own_budget if role == "buyer" else None
    current = None
    if offer is not None:
        current = {"transfer": offer.reserved_transfer_amount, "wage": offer.reserved_wage_weekly}
        merged = _offer_terms(offer)
        merged["add_ons"] = offer.add_ons
        merged.update({k: v for k, v in terms.items() if v is not None})
        terms = merged
    if terms.get("deal_type") == "LOAN" and terms.get("wage_weekly") is None:
        # A loan's wage is his contract wage, filled in by the offer paths
        # (offers.service.loan_wage_basis); the draft never carries it. Read
        # here for the arithmetic only, so the money panel matches the
        # refusal; it is not put into any model's facts.
        from app.players.models import Contract
        contract_wage = (await db.execute(
            select(Contract.wage_weekly).where(Contract.player_id == player_id, Contract.is_active.is_(True))
        )).scalars().first()
        terms = {**terms, "wage_weekly": _num(contract_wage)}
    money = money_effect(terms, role=role, budget=own_budget, reserved=current)
    money["requires_approval"] = False
    if user is not None and club is not None:
        from app.approvals.service import approval_required
        from app.deals.models import DealType
        from app.offers.service import approval_amount

        def dec(v):
            return Decimal(str(v)) if v is not None else None
        amount = approval_amount(
            deal_type=DealType.LOAN if terms.get("deal_type") == "LOAN" else DealType.PERMANENT,
            fee_amount=dec(terms.get("fee_amount")), loan_fee=dec(terms.get("loan_fee")),
            option_to_buy=dec(terms.get("option_to_buy")), obligation_to_buy=bool(terms.get("obligation_to_buy")),
            clauses=terms.get("clauses") or None,
        )
        money["requires_approval"] = await approval_required(db, current_user=user, club=club, amount=amount)
    return {
        "role": role,
        "warnings": check_terms(
            terms, role=role, player=player, budget=budget,
            guide_price=await _guide_price(db, player_id), current=current,
        ),
        "money": money,
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
    from app.common.masking import buyer_is_masked

    return buyer_is_masked(offer, viewer_club_id)


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
    player = await _player_facts(db, offer.player_id, viewer_club_id)
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
    other_name = (("an undisclosed club" if _masked(offer, viewer_club_id) else offer.from_club.name)
                  if role == "seller" else (offer.to_club.name if offer.to_club else "the selling club"))
    # Who made the terms on the table: the last club to act, else the buyer
    # who sent the offer. Spelled out, because a model left to infer it from
    # role and turn got it backwards.
    last_actor = offer.last_actor_club_id or offer.from_club_id
    terms_from = "you" if last_actor == viewer_club_id else "them"

    facts: dict = {
        "currency": CURRENCY,
        "viewer_role": role,
        "you_are": f"the {'buying' if role == 'buyer' else 'selling'} club",
        "current_terms_were_sent_by": terms_from,
        "waiting_for": ("you to accept, counter or reject" if your_turn
                        else f"{other_name} to reply" if offer.status in (OfferStatus.SENT, OfferStatus.COUNTERED)
                        else "nobody: the offer is closed"),
        "status": offer.status.value,
        "your_turn": your_turn,
        "counter_rounds_so_far": rounds,
        "expires_in_days": round((expires - datetime.now(timezone.utc)).total_seconds() / 86400, 1) if expires else None,
        "other_club": other_name,
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
        current={"transfer": offer.reserved_transfer_amount, "wage": offer.reserved_wage_weekly},
    )
    if not facts["your_turn"]:
        # Nothing to decide: say where it stands from the facts, without a
        # model call (and without using the user's AI allowance).
        return {**_waiting_advice(facts), "checks": checks, "facts": _public_offer_facts(facts), "cached": False}

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
            "watch_outs": useful_tips(_strs(data.get("watch_outs"), 3), limit=3),
        }

    result, cached = await _cached(key, produce)
    return {**result, "checks": checks, "facts": _public_offer_facts(facts), "cached": cached}


def _waiting_advice(facts: dict) -> dict:
    """The advisor's answer when it is the other club's move, in code."""
    terms = facts["current_terms"]
    loan = terms.get("deal_type") == "LOAN"
    fee = terms.get("loan_fee") if loan else terms.get("fee_amount")
    player = facts["player"].get("name") or "the player"
    other = facts["other_club"] or "the other club"
    what = (f"a {_short_money(fee)} {'loan' if loan else 'offer'}" if fee
            else ("a loan" if loan else "an offer"))
    if facts["status"] not in ("SENT", "COUNTERED"):
        summary = f"This offer for {player} is {facts['status'].lower()}, so there is nothing to answer."
    elif facts["current_terms_were_sent_by"] == "you":
        summary = f"You sent {what} for {player}. It's {other}'s move: they can accept, counter or reject it."
    else:
        summary = f"These terms for {player} are with {other}, so it's their move."
    reasons = []
    expires = facts.get("expires_in_days")
    if expires is not None and facts["status"] in ("SENT", "COUNTERED"):
        reasons.append(f"It expires in {expires:g} day{'' if expires == 1 else 's'} if they don't answer."
                       if expires > 0 else "It is due to expire now if they don't answer.")
    model = facts["player"].get("fee_model") or {}
    pct = facts.get("fee_vs_model_pct")
    if fee and pct is not None and model.get("fair_value"):
        side = "above" if pct >= 0 else "below"
        reasons.append(f"The {_short_money(fee)} fee is {abs(pct):.0f}% {side} the model's fair value of "
                       f"{_short_money(model['fair_value'])}"
                       + (f" (range {_short_money(model['range_low'])}–{_short_money(model['range_high'])})."
                          if model.get("range_low") and model.get("range_high") else "."))
    if facts["status"] in ("SENT", "COUNTERED"):
        reasons.append("If they counter, you'll be able to answer here, and the advisor will weigh their terms.")
    return {"summary": summary, "recommendation": "wait", "suggested_terms": None,
            "reasons": reasons, "watch_outs": []}


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


def deal_steps(deal, viewer_club_id: uuid.UUID, player_has_account: bool | None = None,
               negotiation=None) -> list[dict]:
    """What the deal is waiting on, and who must act — worked out from the
    stage machine, not by the model. Owners: "you", "them", "either",
    "player", "agent", "staff".

    `player_has_account`: whether the player can answer personal terms
    himself. With no account and no agent, the buying club records his
    answer (product ADR 0006), so that step is the buyer's. Unknown (None)
    is shown as the player's.

    `negotiation`: the deal's AgentNegotiation, if loaded. At that stage the
    agent proposes the commission first, then the buying club answers, then
    either club moves the deal on (deals.service.advance_deal); without it,
    the step is shown as the buying club's, as before."""
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
        agreement = getattr(getattr(negotiation, "club_agreement", None), "value", None) if negotiation else None
        proposed = negotiation is not None and (
            negotiation.commission_pct is not None or negotiation.commission_amount is not None)
        if negotiation is not None and not proposed:
            steps.append({"label": "Propose the commission terms", "owner": "agent"})
        elif agreement == "AGREED":
            steps.append({"label": "Move the deal on to personal terms", "owner": "either"})
        elif negotiation is not None:
            steps.append({"label": "Answer the agent's commission proposal", "owner": owner_of("buyer")})
        else:
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
        elif getattr(pt, "agent_id", None) is not None:
            steps.append({"label": "Get the player's answer on the proposed terms", "owner": "agent"})
        elif player_has_account is False:
            steps.append({
                "label": "Record the player's answer, with the signed terms",
                "owner": owner_of("buyer"),
            })
        else:
            steps.append({"label": "Get the player's answer on the proposed terms", "owner": "player"})
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
    from app.players.service import player_has_account

    negotiation = None
    if deal.stage.value == "AGENT_NEGOTIATION":
        from app.agents.models import AgentNegotiation
        negotiation = (await db.execute(
            select(AgentNegotiation).where(AgentNegotiation.deal_id == deal.id)
        )).scalar_one_or_none()
        if negotiation is None:
            # Invited but not yet started: the agent opens it with a proposal.
            from types import SimpleNamespace
            negotiation = SimpleNamespace(commission_pct=None, commission_amount=None, club_agreement=None)
    steps = deal_steps(deal, viewer_club_id, await player_has_account(db, deal.player_id), negotiation)
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
            "personal_terms_consent": (
                deal.personal_terms.player_consent.value if deal.personal_terms is not None
                and hasattr(deal.personal_terms.player_consent, "value")
                else (deal.personal_terms.player_consent if deal.personal_terms is not None else None)
            ),
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


_FILLER = re.compile(
    r"\b(act (today|now|promptly|quickly)|promptly|without delay|as soon as possible|asap|"
    r"avoid (any |unnecessary )?(delay|delays)|delays? (risks?|could|may)|risks? (stalling|the move stalling)|"
    r"keep (the )?(lines of )?communication|communicate clearly|stay in (close )?contact|keep .{0,20} informed|"
    r"no deadline is set|only outstanding step|(it is|it's) yours)\b",
    re.IGNORECASE,
)


def _words(text: str) -> set[str]:
    """Content words, crudely stemmed ("records" and "record" match)."""
    return {re.sub(r"(ing|ed|s)$", "", w) for w in re.findall(r"[a-z]+", text.lower()) if len(w) > 3}


def useful_tips(tips: list[str], *, steps: list[dict] | None = None, limit: int = 2) -> list[str]:
    """The model's tips, less filler: drop a tip that is generic (`_FILLER`)
    or that mostly restates an outstanding step's label. Applied in code
    because a prompt rule alone is not reliably followed."""
    labels = [_words(s.get("label", "")) for s in steps or []]
    out = []
    for tip in tips:
        words = _words(tip)
        if _FILLER.search(tip) or len(words) < 3:
            continue
        if any(lw and len(words & lw) >= max(2, round(0.6 * len(lw))) and len(words - lw) <= 6 for lw in labels):
            continue
        out.append(tip)
    return out[:limit]


async def _deal_brief(facts: dict, role: str, user_id: uuid.UUID) -> dict:
    data = await _llm_json("DEAL_BRIEF_USER", user_id=user_id, endpoint="deal-brief", max_tokens=400,
                           role=role, facts_json=_dumps(facts))
    return {"headline": str(data.get("headline", "")).strip(),
            "advice": useful_tips(_strs(data.get("advice"), 3), steps=facts.get("outstanding_steps"))}


# ── Drafts: the assistant writes, the user edits and sends ───────────────────

DRAFT_KINDS = ("deal_message", "counter_note", "enquiry_reply")
_MONEY = re.compile(r"£\s?(\d[\d,]*(?:\.\d+)?)\s?(m|k|bn)?", re.IGNORECASE)


def _figures(value) -> set[float]:
    """Every number in the facts, to check a draft's money against."""
    out: set[float] = set()
    if isinstance(value, bool):
        return out
    if isinstance(value, (int, float)):
        out.add(float(value))
    elif isinstance(value, dict):
        for v in value.values():
            out |= _figures(v)
    elif isinstance(value, list):
        for v in value:
            out |= _figures(v)
    return out


def keep_known_figures(text: str, facts: dict) -> str:
    """Drop any sentence quoting a £ figure that is not in the facts (within
    5%, for rounding such as £5.7m for 5,700,000): TransferX computes the
    figures, the model only words them (ADR 0006)."""
    known = [f for f in _figures(facts) if f > 0]
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    kept = []
    for sentence in sentences:
        ok = True
        for amount, unit in _MONEY.findall(sentence):
            v = float(amount.replace(",", "")) * {"m": 1e6, "k": 1e3, "bn": 1e9}.get(unit.lower(), 1)
            if not any(abs(v - f) <= 0.05 * f for f in known):
                ok = False
                break
        if ok:
            kept.append(sentence)
    return " ".join(kept).strip()


async def draft_facts(db: AsyncSession, *, kind: str, ref_id: uuid.UUID, club, channel: str | None = None) -> tuple[dict, str, dict]:
    """(facts, purpose, masks) for a draft. Only what the recipients may be
    told: never the club's budget or a rival's bid, and an undisclosed club
    stays undisclosed. `masks` maps a hidden club name to its label, so the
    draft can be cleaned if the model slips. LookupError if the club may not
    see the subject."""
    masks: dict = {}
    if kind == "deal_message":
        from app.deals.room_models import CommentAudience, DealComment
        from app.deals.service import get_deal_by_id

        deal = await get_deal_by_id(db, ref_id)
        if deal is None or club.id not in (deal.buyer_club_id, deal.seller_club_id):
            raise LookupError("Deal not found")
        side = "buyer" if club.id == deal.buyer_club_id else "seller"
        own_channel = "BUYER_ONLY" if side == "buyer" else "SELLER_ONLY"
        audience = {"SHARED": "SHARED", "CLUB_ONLY": own_channel, own_channel: own_channel}.get(channel or "SHARED", "SHARED")
        other = deal.seller_club if side == "buyer" else deal.buyer_club
        comments = (await db.execute(
            select(DealComment).where(DealComment.deal_id == deal.id, DealComment.audience == CommentAudience(audience))
            .order_by(DealComment.created_at.desc()).limit(6)
        )).scalars().all()
        from app.deals.service import deal_agent

        agent = await deal_agent(db, deal)
        facts = {
            "currency": CURRENCY, "your_club": club.name,
            "your_side": "buying club" if side == "buyer" else "selling club",
            "other_club": other.name if other else None,
            "player": deal.player.name if deal.player else None,
            "player_agent": f"{agent['display_name']} ({agent['agency_name']})" if agent else None,
            "stage": deal.stage.value, "agreed_fee": _num(deal.agreed_fee),
            "outstanding_steps": deal_steps(deal, club.id),
            "recent_messages": [c.body[:300] for c in reversed(comments)],
        }
        purpose = ("a message in the deal room, seen by both clubs and the player's agent"
                   if audience == "SHARED" else "an internal note in the deal room, seen only by your own club")
        return facts, purpose, masks

    if kind == "counter_note":
        offer = await _load_offer(db, ref_id, club.id)
        full = await offer_facts(db, offer, club.id)
        if _masked(offer, club.id) and offer.from_club is not None:
            masks[offer.from_club.name] = "an undisclosed club"
        model = full["player"].get("fee_model") or {}
        facts = {
            "currency": CURRENCY, "your_club": club.name, "your_side": full["viewer_role"] + " club",
            "other_club": full["other_club"],
            "player": {k: full["player"].get(k) for k in ("name", "age", "position", "contract_ends")},
            "current_terms": full["current_terms"], "status": full["status"],
            "counter_rounds_so_far": full["counter_rounds_so_far"],
            "model_range": [model.get("range_low"), model.get("range_high")] if model else None,
            "listing_guide_price": full["listing_guide_price"],
            "recent_messages": [m.body[:300] for m in sorted(offer.messages, key=lambda m: m.created_at)[-6:]],
        }
        return facts, "a message to the other club on the offer, explaining the current terms", masks

    if kind == "enquiry_reply":
        from app.enquiries.models import Enquiry

        enquiry = (await db.execute(
            select(Enquiry).where(Enquiry.id == ref_id).options(
                selectinload(Enquiry.messages), selectinload(Enquiry.player),
                selectinload(Enquiry.from_club), selectinload(Enquiry.to_club))
        )).scalar_one_or_none()
        if enquiry is None or club.id not in (enquiry.from_club_id, enquiry.to_club_id):
            raise LookupError("Enquiry not found")
        asking = club.id == enquiry.from_club_id
        other = enquiry.to_club if asking else enquiry.from_club
        other_label = other.name if other else None
        if not asking and enquiry.is_anonymous and other is not None:
            league = getattr(other, "masking_league", None)
            other_label = f"an undisclosed {league} club" if league else "an undisclosed club"
            masks[other.name] = other_label
        facts = {
            "your_club": club.name, "your_side": "asking club" if asking else "the player's club",
            "other_club": other_label, "player": enquiry.player.name if enquiry.player else None,
            "status": enquiry.status.value,
            "messages": [{"from": "you" if m.sender_club_id == club.id else "them", "text": m.body[:300]}
                         for m in sorted(enquiry.messages, key=lambda m: m.created_at)[-8:]],
        }
        return facts, "a reply in an enquiry about a player", masks

    raise ValueError("Unknown draft kind")


async def draft_message(db: AsyncSession, *, kind: str, ref_id: uuid.UUID, club, user,
                        channel: str | None = None, intent: str | None = None) -> dict:
    """A message for the user to edit and send themselves (ADR 0006): never
    sent from here. Hidden club names are masked and unknown figures dropped
    in code, whatever the model wrote."""
    import hashlib

    if kind not in DRAFT_KINDS:
        raise ValueError("Unknown draft kind")
    facts, purpose, masks = await draft_facts(db, kind=kind, ref_id=ref_id, club=club, channel=channel)
    intent = (intent or "").strip().replace('"', "'")[:300]
    fingerprint = hashlib.sha1((kind + intent + _dumps(facts)).encode()).hexdigest()[:16]

    async def produce():
        data = await _llm_json("DRAFT_MESSAGE_USER", user_id=user.id, endpoint=f"draft-{kind}", max_tokens=500,
                               club_name=club.name, purpose=purpose, intent=intent, facts_json=_dumps(facts))
        return str(data.get("text", "")).strip()

    text, _ = await _cached(f"draft:{user.id}:{ref_id}:{fingerprint}", produce, ttl=300)
    for real, label in masks.items():
        text = re.sub(re.escape(real), label, text, flags=re.IGNORECASE)
    text = keep_known_figures(text, facts)[:1500]
    if not text:
        raise RuntimeError("The assistant couldn't write a usable draft. Try again, or say what you want to say.")
    return {"kind": kind, "text": text}


# ── Phase 2b: morning briefing ───────────────────────────────────────────────


async def briefing_facts(db: AsyncSession, club, user) -> dict:
    from app.dashboard import service as dashboard_service
    from app.notifications.models import Notification
    from app.players.models import Player

    waiting = (await dashboard_service.get_dashboard(db, club=club, current_user=user)).waiting_on_you
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    recent = (await db.execute(
        select(Notification).where(Notification.recipient_user_id == user.id, Notification.created_at >= since)
        .order_by(Notification.created_at.desc()).limit(15)
    )).scalars().all()
    soon = date.today() + timedelta(days=183)
    squad = (await db.execute(select(Player).where(Player.current_club_id == club.id))).scalars().all()
    ends = await _contract_ends(db, squad)
    expiring = sorted((p for p in squad if ends.get(p.id) and ends[p.id] <= soon), key=lambda p: ends[p.id])[:6]
    return {
        "currency": CURRENCY,
        "today": date.today().isoformat(),
        "waiting_on_you": [
            {"what": i.reason, "player": i.player_name, "club": i.club_name,
             "deadline": i.deadline.isoformat() if getattr(i, "deadline", None) else None, "path": i.link}
            for i in waiting[:10]
        ],
        "last_24_hours": [n.message for n in recent],
        "contracts_ending_within_6_months": [
            {"player": p.name, "ends": ends[p.id].isoformat()} for p in expiring
        ],
        "budget": await _budget_facts(db, club.id),
    }


async def club_briefing(db: AsyncSession, club, user) -> dict | None:
    """Today's AI briefing for one person at a club, or None without a model.
    Cached per user and day, refreshed when what is waiting on them changes."""
    import hashlib

    if not ai_available():
        return None
    facts = await briefing_facts(db, club, user)
    fingerprint = hashlib.sha1(_dumps(facts["waiting_on_you"]).encode()).hexdigest()[:12]

    async def produce():
        data = await _llm_json("CLUB_BRIEFING_USER", user_id=user.id, endpoint="club-briefing", max_tokens=500,
                               club_name=club.name, facts_json=_dumps(facts))
        return {
            "headline": str(data.get("headline", "")).strip(),
            "focus": str(data.get("focus", "")).strip(),
            "points": useful_tips(_strs(data.get("points"), 5), limit=5),
        }

    result, cached = await _cached(f"briefing:{user.id}:{date.today()}:{fingerprint}", produce, ttl=12 * 3600)
    return {**result, "waiting_count": len(facts["waiting_on_you"]), "cached": cached}


# ── Phase 3a: listing assistant ──────────────────────────────────────────────


def _round_price(v: float) -> float:
    step = 250_000 if v >= 2_000_000 else 50_000
    return max(step, round(v / step) * step)


async def _comparables(db: AsyncSession, player: dict, exclude_player_id: uuid.UUID) -> list[dict]:
    """Completed permanent transfers of similar players in the last 18
    months — public on Recent Transfers."""
    from app.deals.models import Deal, DealStatus, DealType
    from app.players.models import Player, PlayerPosition

    if not player.get("position"):
        return []
    since = datetime.now(timezone.utc) - timedelta(days=548)
    q = (
        select(Deal, Player).join(Player, Player.id == Deal.player_id)
        .where(Deal.status == DealStatus.COMPLETED, Deal.deal_type == DealType.PERMANENT,
               Deal.completed_at >= since, Deal.agreed_fee > 0,
               Player.position == PlayerPosition(player["position"]), Player.id != exclude_player_id)
    )
    age = player.get("age")
    if age:
        q = q.where(Player.age.between(age - 3, age + 3))
    rows = (await db.execute(q.order_by(Deal.completed_at.desc()).limit(8))).all()
    return [
        {"player": p.name, "age": p.age, "fee": _num(d.agreed_fee),
         "completed": d.completed_at.date().isoformat() if d.completed_at else None}
        for d, p in rows
    ]


async def listing_advice(db: AsyncSession, player_id: uuid.UUID, *, viewer_club_id: uuid.UUID,
                         user_id: uuid.UUID) -> dict:
    from app.offers.models import Offer
    from app.players.models import Player
    from app.sales.models import Sale, SaleStatus

    from app.players.service import get_owning_club_id

    # The owner, as listing resolves it: a club lending a player out still
    # owns him, and a club that created a player with no contract owns him.
    target = (await db.execute(select(Player).where(Player.id == player_id))).scalar_one_or_none()
    if target is None or await get_owning_club_id(db, target) != viewer_club_id:
        raise LookupError("Player not found")
    player = await _player_facts(db, player_id, viewer_club_id)
    comps = await _comparables(db, player, player_id)
    model = player.get("fee_model") or {}
    fair = model.get("fair_value")
    comp_fees = sorted(c["fee"] for c in comps if c["fee"])
    comp_median = comp_fees[len(comp_fees) // 2] if comp_fees else None
    if fair and comp_median:
        guide = 0.6 * fair + 0.4 * comp_median
        basis = "model and comparable transfers"
    elif fair:
        guide, basis = fair, "model"
    elif comp_median:
        guide, basis = comp_median, "comparable transfers"
    else:
        guide, basis = None, None
    months = player.get("months_left_on_contract")
    if guide and months is not None and months <= 12:
        guide *= 0.7  # a player who can leave for nothing within a year sells for less
        basis += ", reduced for his contract ending within 12 months"
    guide = _round_price(guide) if guide else None

    listing = None
    sale = (await db.execute(
        select(Sale).where(Sale.player_id == player_id, Sale.status == SaleStatus.OPEN)
    )).scalars().first()
    if sale is not None:
        offers = (await db.execute(select(Offer.id).where(Offer.sale_id == sale.id))).all()
        listing = {
            "days_listed": (datetime.now(timezone.utc) - _utc(sale.created_at)).days,
            "guide_price": _num(sale.asking_price),
            "availability": sale.availability.value,
            "offers_received": len(offers),
        }
    age = player.get("age") or 99
    default_availability = "EITHER" if age <= 21 else "TRANSFER"
    result = {
        "guide_price": guide,
        "guide_basis": basis,
        "comparables": comps,
        "listing": listing,
        "availability": default_availability,
        "summary": None,
        "reasons": [],
        "tips": [],
    }
    if not ai_available():
        return result
    facts = {"currency": CURRENCY, "player": player, "computed_guide_price": guide, "guide_basis": basis,
             "comparable_transfers": comps, "current_listing": listing}
    key = f"listing:{player_id}:{guide}:{_dumps(listing)}"

    async def produce():
        data = await _llm_json("LISTING_ADVICE_USER", user_id=user_id, endpoint="listing-advice",
                               max_tokens=500, facts_json=_dumps(facts))
        availability = str(data.get("availability", "")).upper()
        return {
            "summary": str(data.get("summary", "")).strip() or None,
            "availability": availability if availability in ("TRANSFER", "LOAN", "EITHER") else default_availability,
            "reasons": _strs(data.get("reasons"), 4),
            "tips": useful_tips(_strs(data.get("tips"), 3), limit=3),
        }

    try:
        ai, _ = await _cached(key, produce)
        result.update(ai)
    except Exception as exc:
        logger.warning("Listing advice narrative unavailable: %s", exc)
    return result


# ── Phase 3b: who might want him ─────────────────────────────────────────────

# A squad's usual depth per position; fewer than this is a gap.
_TYPICAL_DEPTH = {"GK": 3, "DEF": 8, "MID": 8, "FWD": 6}


async def potential_buyers(db: AsyncSession, player_id: uuid.UUID, *, viewer_club_id: uuid.UUID,
                           user_id: uuid.UUID) -> dict:
    """Clubs on TransferX whose squads suggest a need for this player. Uses
    public squad information only — never another club's budget."""
    from app.clubs.models import Club
    from app.players.models import Player

    from app.players.service import get_owning_club_id

    target = (await db.execute(select(Player).where(Player.id == player_id))).scalar_one_or_none()
    if target is None or await get_owning_club_id(db, target) != viewer_club_id:
        raise LookupError("Player not found")
    if target.position is None:
        return {"summary": "He has no position recorded, so there is nothing to match on.", "clubs": []}
    pos = target.position.value
    clubs = (await db.execute(select(Club).where(Club.id != viewer_club_id))).scalars().all()
    from sqlalchemy import func

    sizes = dict((await db.execute(
        select(Player.current_club_id, func.count()).where(Player.current_club_id.in_([c.id for c in clubs]))
        .group_by(Player.current_club_id)
    )).all())
    # A club with no real squad on TransferX (a test or just-joined account)
    # tells us nothing about need.
    clubs = [c for c in clubs if sizes.get(c.id, 0) >= 11]
    players = (await db.execute(
        select(Player).where(Player.current_club_id.in_([c.id for c in clubs]), Player.position == target.position)
    )).scalars().all()
    ends = await _contract_ends(db, players)
    by_club: dict[uuid.UUID, list] = {}
    for p in players:
        by_club.setdefault(p.current_club_id, []).append(p)
    horizon = date.today() + timedelta(days=365)
    candidates = []
    for club in clubs:
        squad = by_club.get(club.id, [])
        ages = [p.age for p in squad if p.age]
        expiring = sum(1 for p in squad if ends.get(p.id) and ends[p.id] <= horizon)
        over_31 = sum(1 for a in ages if a >= 31)
        depth = len(squad)
        avg_age = sum(ages) / len(ages) if ages else None
        need = (max(0, _TYPICAL_DEPTH.get(pos, 6) - depth) * 2 + expiring + over_31
                + (1 if avg_age and avg_age >= 29 else 0))
        if need <= 0:
            continue
        candidates.append({
            "club_id": str(club.id), "club": club.name, "league": club.league_name,
            "players_in_position": depth, "average_age_in_position": round(avg_age, 1) if avg_age else None,
            "contracts_ending_within_12_months": expiring, "aged_31_or_over": over_31, "need_score": need,
        })
    candidates.sort(key=lambda c: -c["need_score"])
    top = candidates[:10]

    def plain(c: dict) -> str:
        bits = [f"{c['players_in_position']} {pos} in the squad"]
        if c["contracts_ending_within_12_months"]:
            bits.append(f"{c['contracts_ending_within_12_months']} out of contract within a year")
        if c["aged_31_or_over"]:
            bits.append(f"{c['aged_31_or_over']} aged 31+")
        return "; ".join(bits).capitalize() + "."

    fallback = {
        "summary": None if top else f"No club on TransferX looks short of a {pos} right now — listing him lets any club find him.",
        "clubs": [{"club_id": c["club_id"], "club": c["club"], "reason": plain(c)} for c in top[:5]],
    }
    if not top or not ai_available():
        return fallback
    facts = {"player": {"name": target.name, "age": target.age, "position": pos},
             "candidate_clubs": [{k: v for k, v in c.items() if k != "need_score"} for c in top]}

    async def produce():
        data = await _llm_json("POTENTIAL_BUYERS_USER", user_id=user_id, endpoint="potential-buyers",
                               max_tokens=600, facts_json=_dumps(facts))
        known = {c["club_id"]: c for c in top}
        picked = []
        for row in data.get("clubs") or []:
            cid = str(row.get("club_id", ""))
            if cid in known and cid not in {p["club_id"] for p in picked}:
                picked.append({"club_id": cid, "club": known[cid]["club"], "reason": str(row.get("reason", "")).strip() or plain(known[cid])})
        return {"summary": str(data.get("summary", "")).strip() or None, "clubs": picked[:5] or fallback["clubs"]}

    try:
        result, _ = await _cached(f"buyers:{player_id}:{date.today()}", produce, ttl=12 * 3600)
        return result
    except Exception as exc:
        logger.warning("Potential buyers narrative unavailable: %s", exc)
        return fallback


# ── Phase 3c: Ask TransferX ──────────────────────────────────────────────────


async def ask_facts(db: AsyncSession, club, user) -> dict:
    """The viewer's own club data, each item with the page it lives on."""
    from app.deals.models import Deal, DealStatus
    from app.enquiries.models import Enquiry, EnquiryStatus
    from app.offers.models import Offer, OfferStatus
    from app.players.models import Player
    from app.sales.models import Sale, SaleStatus

    active = [OfferStatus.SENT, OfferStatus.COUNTERED]
    received = (await db.execute(
        select(Offer).where(Offer.to_club_id == club.id, Offer.status.in_(active))
        .options(selectinload(Offer.player), selectinload(Offer.from_club)).limit(30)
    )).scalars().all()
    sent = (await db.execute(
        select(Offer).where(Offer.from_club_id == club.id, Offer.status.in_(active))
        .options(selectinload(Offer.player), selectinload(Offer.to_club)).limit(30)
    )).scalars().all()
    from app.dashboard import service as dashboard_service

    waiting = (await dashboard_service.get_dashboard(db, club=club, current_user=user)).waiting_on_you
    deals = (await db.execute(
        select(Deal).where(
            (Deal.buyer_club_id == club.id) | (Deal.seller_club_id == club.id),
            Deal.status.in_([DealStatus.IN_PROGRESS, DealStatus.PENDING_COMPLETION]),
        ).options(selectinload(Deal.player), selectinload(Deal.buyer_club), selectinload(Deal.seller_club),
                  selectinload(Deal.personal_terms), selectinload(Deal.medical_check)).limit(30)
    )).scalars().all()
    listings = (await db.execute(
        select(Sale).where(Sale.seller_club_id == club.id, Sale.status == SaleStatus.OPEN)
        .options(selectinload(Sale.player)).limit(30)
    )).scalars().all()
    enquiries = (await db.execute(
        select(Enquiry).where((Enquiry.from_club_id == club.id) | (Enquiry.to_club_id == club.id),
                              Enquiry.status == EnquiryStatus.OPEN)
        .options(selectinload(Enquiry.player)).limit(30)
    )).scalars().all()
    squad = (await db.execute(select(Player).where(Player.current_club_id == club.id))).scalars().all()
    ends = await _contract_ends(db, squad)

    def exp(o) -> str | None:
        return _utc(o.expires_at).date().isoformat() if o.expires_at else None

    def whose(o) -> str:
        return "theirs" if o.last_actor_club_id == club.id else "yours"

    return {
        "currency": CURRENCY,
        "today": date.today().isoformat(),
        "club": club.name,
        "budget": await _budget_facts(db, club.id),
        "budget_note": ("transfer_budget_remaining is what is free now: money held for open offers and committed "
                        "to transfers in progress is already taken off it"),
        "offers_received": [
            {"player": o.player.name if o.player else None,
             "from": "an undisclosed club" if o.is_anonymous else (o.from_club.name if o.from_club else None),
             "type": o.deal_type.value, "fee": _num(o.fee_amount), "loan_fee": _num(o.loan_fee),
             "status": o.status.value, "move": whose(o), "expires": exp(o), "path": f"/offers/{o.id}"}
            for o in received
        ],
        "offers_sent": [
            {"player": o.player.name if o.player else None, "to": o.to_club.name if o.to_club else None,
             "type": o.deal_type.value, "fee": _num(o.fee_amount), "loan_fee": _num(o.loan_fee),
             "status": o.status.value, "move": whose(o), "expires": exp(o), "path": f"/offers/{o.id}"}
            for o in sent
        ],
        "transfers_in_progress": [
            {"player": d.player.name if d.player else None,
             "side": "buying" if d.buyer_club_id == club.id else "selling",
             "other_club": (d.seller_club.name if d.buyer_club_id == club.id and d.seller_club
                            else d.buyer_club.name if d.buyer_club else None),
             "stage": d.stage.value, "fee": _num(d.agreed_fee),
             "next_steps": [f"{s['label']} ({s['owner']})" for s in deal_steps(d, club.id)],
             "path": f"/deals/{d.id}"}
            for d in deals
        ],
        # The Dashboard's own list: exactly what is waiting on this person now.
        "waiting_on_you": [
            {"what": i.reason, "player": i.player_name, "club": i.club_name, "path": i.link} for i in waiting
        ],
        "your_listings": [
            {"player": s.player.name if s.player else None, "type": s.sale_type.value,
             "availability": s.availability.value, "guide_price": _num(s.asking_price),
             "deadline": _utc(s.deadline).date().isoformat() if s.deadline else None, "path": f"/sales/{s.id}"}
            for s in listings
        ],
        "open_enquiries": [
            {"player": e.player.name if e.player else None,
             "side": "you asked" if e.from_club_id == club.id else "about your player",
             "path": f"/enquiries/{e.id}"}
            for e in enquiries
        ],
        "squad": [
            {"player": p.name, "position": p.position.value if p.position else None, "age": p.age,
             "contract_ends": ends[p.id].isoformat() if ends.get(p.id) else None,
             "listed": p.open_to_offers, "path": f"/players/market/{p.id}"}
            for p in squad
        ][:60],
        "pages": [
            {"label": "Dashboard", "path": "/dashboard"}, {"label": "Browse players", "path": "/players/market"},
            {"label": "Listings", "path": "/sales"}, {"label": "My listings", "path": "/sales/mine"},
            {"label": "Offers received", "path": "/offers/received"}, {"label": "My offers", "path": "/offers/sent"},
            {"label": "Transfers in progress", "path": "/deals"}, {"label": "Enquiries", "path": "/enquiries"},
            {"label": "My club", "path": "/club"}, {"label": "Finance", "path": "/club/finance"},
        ],
    }


def _paths(facts: dict) -> set[str]:
    found: set[str] = set()

    def walk(v):
        if isinstance(v, dict):
            if isinstance(v.get("path"), str):
                found.add(v["path"])
            for x in v.values():
                walk(x)
        elif isinstance(v, list):
            for x in v:
                walk(x)

    walk(facts)
    return found


LITE_PAGES = [
    {"label": "Lite home", "path": "/lite"},
    {"label": "Buy a player", "path": "/lite/buy"},
    {"label": "Answer offers", "path": "/lite/offers"},
    {"label": "Ask anything", "path": "/lite/ask"},
]
_LITE_POSITIONS = {"GK": "goalkeepers", "DEF": "defenders", "MID": "midfielders", "FWD": "forwards"}
_LITE_BANDS = {"0-5": "up to £5m", "5-10": "£5m to £10m", "10-20": "£10m to £20m", "free": "free or on loan"}
PROPOSAL_KINDS = ("bid", "counter", "accept", "reject")
_CANT = re.compile(r"\b(don't|do not|doesn't|does not|can't|cannot|no) (have|show|include|contain|information|data|answer)", re.I)


def lite_ask_facts(facts: dict) -> dict:
    """Lite pages and the Buy flow's results pages, so the model can link to
    them (it may only use paths that appear in the facts)."""
    searches = [{"label": f"{word.capitalize()}, {band}", "path": f"/lite/buy/results?position={pos}&budget={key}"}
                for pos, word in _LITE_POSITIONS.items() for key, band in _LITE_BANDS.items()]
    return {**facts, "pages": LITE_PAGES + facts["pages"], "lite_player_searches": searches}


def _short_money(v: float) -> str:
    return f"£{v / 1e6:.1f}m".replace(".0m", "m") if v >= 1e6 else f"£{v / 1e3:.0f}k"


_PROPOSAL_ANSWER = {
    "bid": lambda p: f"I've prepared a {_short_money(p['amount'])} bid for {p['player']} ({p['club']}) for you to check.",
    "counter": lambda p: f"I've prepared a counter at {_short_money(p['amount'])} for {p['player']} for you to check.",
    "accept": lambda p: f"I've opened the offer for {p['player']} ready to accept, for you to check.",
    "reject": lambda p: f"I've opened the offer for {p['player']} ready to turn down, for you to check.",
}


async def resolve_proposal(db: AsyncSession, raw, *, facts: dict, club, user) -> tuple[dict | None, list[dict], str | None]:
    """The model's proposal, checked in code (BACKEND.md §3): a known kind,
    a player or offer this club may act on, an amount within half and double
    the known figures, and a role allowed to do it. Returns (proposal or
    None, links, reason): an ambiguous player gives no proposal and one link
    per candidate, and `reason` says in plain words why it couldn't be
    prepared. Nothing is sent; the card it opens is confirmed by the user."""
    if not isinstance(raw, dict) or raw.get("kind") not in PROPOSAL_KINDS:
        return None, [], None
    from app.clubs.capabilities import Capability, capabilities_for_role
    from app.clubs.service import get_club_and_role_for_user

    _, role = await get_club_and_role_for_user(db, user.id)
    if not user.is_superuser and Capability.MARKET_WRITE not in capabilities_for_role(role or "OWNER"):
        return None, [], "Your role can't send or answer offers. Ask your club's owner."
    kind = raw["kind"]
    try:
        amount = float(raw["amount"]) if raw.get("amount") is not None else None
    except (TypeError, ValueError):
        amount = None

    if kind == "bid":
        from app.clubs.models import Club
        from app.lite.service import _round_half_m, player_prices
        from app.players.models import Player, PlayerStatus
        from app.players.service import get_owning_club_id

        name = str(raw.get("player") or "").strip()
        if len(name) < 2:
            return None, [], "I couldn't tell which player you meant."
        found = (await db.execute(
            select(Player).where(Player.name.ilike(f"%{name}%"),
                                 Player.status.in_([PlayerStatus.CONTRACTED, PlayerStatus.FREE_AGENT]))
            .order_by(Player.name).limit(6)
        )).scalars().all()
        exact = [p for p in found if p.name.lower() == name.lower()]
        candidates = exact or found
        if len(candidates) != 1:
            return (None, [{"label": p.name, "path": f"/players/market/{p.id}"} for p in candidates[:3]],
                    f"More than one player matches “{name}”. Which one did you mean?" if candidates
                    else f"I couldn't find a player called “{name}” that you can make an offer for.")
        player = candidates[0]
        owner = await get_owning_club_id(db, player)
        if owner is None or owner == club.id:
            return None, [{"label": player.name, "path": f"/players/market/{player.id}"}], (
                f"{player.name} is already your player." if owner == club.id
                else f"{player.name} has no club on TransferX to make an offer to.")
        price, _, sale = (await player_prices(db, [player], owned={player.id})).get(player.id, (None, None, None))
        if not price:
            return None, [{"label": player.name, "path": f"/players/market/{player.id}"}], (
                f"TransferX has no price for {player.name} to check a bid against, so make it from his page.")
        if amount is None:
            amount = _round_half_m(price)
        if not (0.5 * price <= amount <= 2 * price):
            return None, [{"label": player.name, "path": f"/players/market/{player.id}"}], (
                f"{_short_money(amount)} is too far from his price of about {_short_money(price)} to prepare. "
                "Open his page to make a different offer.")
        seller = (await db.execute(select(Club.name).where(Club.id == owner))).scalar_one_or_none()
        return {
            "kind": "bid", "player_id": str(player.id), "player": player.name, "club": seller, "amount": amount,
            "prefill": {"player_id": str(player.id), "to_club_id": str(owner),
                        "sale_id": str(sale.id) if sale is not None else None, "fee_amount": amount},
            "card_path": f"/lite/bid?player_id={player.id}&fee={int(amount)}&from=ask",
        }, [], None

    # counter / accept / reject: an open offer in the facts, and the club's move.
    path = str(raw.get("offer_path") or "")
    offer = next((o for o in facts.get("offers_received", []) + facts.get("offers_sent", [])
                  if o.get("path") == path), None)
    if offer is None or offer.get("move") != "yours":
        return None, [], "That offer isn't waiting on you, so there's nothing to answer yet."
    offer_id = path.rsplit("/", 1)[-1]
    if kind == "counter":
        fee = offer.get("fee")
        if offer.get("type") != "PERMANENT" or not fee or amount is None or not (0.5 * fee <= amount <= 2 * fee):
            return None, [{"label": f"Offer for {offer.get('player')}", "path": f"/lite/offers/{offer_id}"}], (
                "I can only prepare a counter on a permanent offer, at a fee between half and double theirs.")
    query = f"action={kind}&from=ask" + (f"&amount={int(amount)}" if kind == "counter" else "")
    return {
        "kind": kind, "offer_id": offer_id, "player": offer.get("player"),
        "club": offer.get("from") or offer.get("to"), "amount": amount if kind == "counter" else offer.get("fee"),
        "prefill": {"fee_amount": amount} if kind == "counter" else {},
        "card_path": f"/lite/offers/{offer_id}?{query}",
    }, [], None


_BID_ASK = [
    # "bid £8m for Ellis Varga", "offer 8m for Varga", "put in a £7.5m bid for Varga"
    re.compile(r"\b(?:bid|offer)\s+£?\s?(?P<amount>\d+(?:\.\d+)?)\s?(?P<unit>m|k|million)?\s+(?:for|on)\s+(?P<player>.+)$", re.I),
    re.compile(r"£?\s?(?P<amount>\d+(?:\.\d+)?)\s?(?P<unit>m|k|million)?\s+(?:bid|offer)\s+(?:for|on)\s+(?P<player>.+)$", re.I),
    # "bid for Ellis Varga" (no amount: his price is used)
    re.compile(r"^(?:please\s+)?(?:make\s+an?\s+|put\s+in\s+an?\s+)?(?:bid|offer)\s+(?:for|on)\s+(?P<player>.+)$", re.I),
]


def bid_from_question(question: str) -> dict | None:
    """A plain bid request, read in code when the model gives no proposal;
    it is then checked by `resolve_proposal` like any other."""
    q = question.strip().rstrip(".?!")
    for pattern in _BID_ASK:
        m = pattern.search(q)
        if m:
            amount = None
            if m.groupdict().get("amount"):
                unit = (m.group("unit") or "m").lower()
                amount = float(m.group("amount")) * (1e3 if unit == "k" else 1e6)
            return {"kind": "bid", "player": m.group("player").strip(), "amount": amount}
    return None


async def _log_question(db: AsyncSession, user, question: str, *, input: str, lite: bool,
                        had_proposal: bool, links_count: int, fallback: bool) -> None:
    from app.ai.models import AssistantQuery

    db.add(AssistantQuery(user_id=user.id, question=question[:500], input=input, lite=lite,
                          had_proposal=had_proposal, links_count=links_count, fallback=fallback))
    await db.flush()


async def ask(db: AsyncSession, club, user, question: str, *, lite: bool = False, input: str = "text") -> dict:
    """Ask TransferX. In Lite, the answer is shorter, can link to Lite pages,
    and can carry a `proposal` that opens an action card. Every question is
    logged (`assistant_queries`); the caller commits."""
    import hashlib

    from app.ai import tracking

    question = question.strip()[:500]
    input = input if input in ("text", "voice") else "text"
    facts = await ask_facts(db, club, user)
    if lite:
        facts = lite_ask_facts(facts)
    allowed = _paths(facts)
    fingerprint = hashlib.sha1((str(lite) + question.lower() + _dumps(facts)).encode()).hexdigest()[:16]

    async def produce():
        data = await _llm_json("ASK_LITE_USER" if lite else "ASK_USER", user_id=user.id, endpoint="ask",
                               max_tokens=600, bucket="ask", club_name=club.name,
                               question=question.replace('"', "'"), facts_json=_dumps(facts))
        links = []
        for row in data.get("links") or []:
            if isinstance(row, dict) and row.get("path") in allowed:
                links.append({"label": str(row.get("label") or row["path"]).strip(), "path": row["path"]})
        return {"answer": str(data.get("answer", "")).strip(), "links": links[:4],
                "raw_proposal": data.get("proposal") if lite else None}

    try:
        result, cached = await _cached(f"ask:{user.id}:{fingerprint}", produce, ttl=600)
    except Exception:
        await _log_question(db, user, question, input=input, lite=lite, had_proposal=False, links_count=0, fallback=True)
        raise
    raw = (result.get("raw_proposal") or bid_from_question(question)) if lite else None
    proposal, extra, reason = (await resolve_proposal(db, raw, facts=facts, club=club, user=user)
                               if lite else (None, [], None))
    links = (result["links"] + [lnk for lnk in extra if lnk not in result["links"]])[:4]
    # The model can't know how the check went, so when it proposed an action
    # the answer comes from code: ready to check, or why it couldn't be.
    if proposal is not None:
        result = {**result, "answer": _PROPOSAL_ANSWER[proposal["kind"]](proposal)}
    elif reason:
        result = {**result, "answer": reason}
    fallback = not result["answer"] or (not links and proposal is None and bool(_CANT.search(result["answer"])))
    await _log_question(db, user, question, input=input, lite=lite, had_proposal=proposal is not None,
                        links_count=len(links), fallback=fallback)
    if proposal is not None:
        await tracking.record_shown(db, "ask_proposal", user.id, ref=proposal.get("player_id") or proposal.get("offer_id"))
    return {"answer": result["answer"], "links": links, "proposal": proposal, "fallback": fallback, "cached": cached}
