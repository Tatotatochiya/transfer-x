"""A player's last transfer fee: what a club actually paid for him last time.

Shown next to the model's value wherever a price is (team feedback,
2026-10-29: "people will recognise true real-life valuations"). The newest
permanent move with a known fee wins:
- API-Football's transfer history (player_transfers), whose fee is a string
  such as "€ 116.6M", converted to pounds at the valuation model's rates;
- a completed TransferX deal, unless it's a demo or test transfer.
Loans, free transfers and moves with no fee on record don't count: they say
nothing about his price.

A later free move is reported separately (`later_free_move`) so the model can
decline to anchor on a fee the player has since left behind.
"""
from __future__ import annotations

import re
import uuid
from collections import defaultdict
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

_FEE_RE = re.compile(r"(?P<cur>€|£|\$|&pound;|&euro;)?\s*(?P<num>\d+(?:[.,]\d+)?)\s*(?P<unit>mln|[MmKkBb])?", re.I)
_UNIT = {"m": 1e6, "mln": 1e6, "k": 1e3, "b": 1e9}
# asyncpg caps a statement at 32,767 bind parameters; keep well below it.
_CHUNK = 500
# Staff-entered rows: a correction, or a fee the vendor never reported.
_MANUAL_VENDOR = "manual"


def fee_gbp(display: str | None) -> float | None:
    """'€ 116.6M' → pounds. A fee with no currency sign is in euros, as
    API-Football's are. None when there's no amount ('Free', 'Loan', 'N/A')."""
    from app.valuation.features_v2 import GBP_PER

    if not display or not any(ch.isdigit() for ch in display):
        return None
    m = _FEE_RE.search(display)
    if not m:
        return None
    amount = float(m.group("num").replace(",", ".")) * _UNIT.get((m.group("unit") or "").lower(), 1.0)
    cur = (m.group("cur") or "€").lower()
    if cur in ("£", "&pound;"):
        return amount
    if cur == "$":
        return amount / GBP_PER["USD"]
    return amount / GBP_PER["EUR"]


def _day(v) -> date | None:
    return v.date() if isinstance(v, datetime) else v


def format_fee_display(amount: float, currency: str) -> str:
    """Inverse of fee_gbp, in the vendor's shape: '£ 105M', '€ 4.5M', '€ 750K'."""
    symbol = {"GBP": "£", "EUR": "€", "USD": "$"}[currency]
    if amount >= 1_000_000:
        return f"{symbol} {amount / 1_000_000:g}M"
    return f"{symbol} {amount / 1_000:g}K"


async def last_transfer_fees(db: AsyncSession, player_ids) -> dict[uuid.UUID, dict]:
    """{player_id: {"fee_gbp", "fee_display", "date", "from", "to", "source",
                    "source_key", "basis"[, "later_free_move"]}}
    for the players with a known last fee; the rest are absent.

    A staff-entered row for the same move (within 60 days) replaces the vendor's
    figure; otherwise the newest dated move wins, as before. `later_free_move`
    is the ISO date of a later permanent free move, when there is one.

    The row is public (the player ledger is open to signed-out visitors), so a
    staff row's source note and URL stay out of it: staff read them from the
    admin endpoints only."""
    from app.clubs.models import Club
    from app.deals.models import Deal, DealStatus, DealType
    from app.demo.service import shared_deals
    from app.players.models import PlayerTransfer

    ids = list(player_ids)
    if not ids:
        return {}
    best: dict[uuid.UUID, dict] = {}
    free_dates: dict[uuid.UUID, list[date]] = defaultdict(list)

    def offer(pid, row):
        if row["date"] is None:
            return
        if pid not in best or row["date"] > best[pid]["date"]:
            best[pid] = row

    for i in range(0, len(ids), _CHUNK):
        chunk = ids[i : i + _CHUNK]
        rows = (await db.execute(select(PlayerTransfer).where(
                PlayerTransfer.player_id.in_(chunk), PlayerTransfer.fee_display.is_not(None),
                PlayerTransfer.transfer_date.is_not(None)))).scalars().all()
        manual_dates: dict[uuid.UUID, list[date]] = defaultdict(list)
        for t in rows:
            if t.vendor == _MANUAL_VENDOR and (t.transfer_type or "").lower() != "loan":
                manual_dates[t.player_id].append(t.transfer_date)
        # Only an explicit "Free" says the old fee no longer describes his
        # market: "N/A" is undisclosed and loan returns are non-loan vendor rows.
        for t in rows:
            if (t.transfer_type or "").lower() == "loan":
                continue
            if (t.fee_display or "").strip().lower().startswith("free"):
                free_dates[t.player_id].append(t.transfer_date)
        for t in rows:
            if (t.transfer_type or "").lower() == "loan":
                continue
            gbp = fee_gbp(t.fee_display)
            if not gbp:
                continue
            if t.vendor == _MANUAL_VENDOR:
                offer(t.player_id, {"fee_gbp": round(gbp), "fee_display": t.fee_display,
                                    "date": t.transfer_date, "from": t.team_out_name,
                                    "to": t.team_in_name, "source": "Staff-entered",
                                    "source_key": "MANUAL", "basis": t.fee_basis or "PERMANENT"})
            elif not any(abs((t.transfer_date - d).days) <= 60
                         for d in manual_dates.get(t.player_id, [])):
                offer(t.player_id, {"fee_gbp": round(gbp), "fee_display": t.fee_display,
                                    "date": t.transfer_date, "from": t.team_out_name,
                                    "to": t.team_in_name, "source": "API-Football",
                                    "source_key": "REPORTED", "basis": "PERMANENT"})

    for i in range(0, len(ids), _CHUNK):
        chunk = ids[i : i + _CHUNK]
        deals = (await db.execute(select(Deal).where(
            Deal.player_id.in_(chunk), Deal.status == DealStatus.COMPLETED,
            Deal.deal_type == DealType.PERMANENT,
            Deal.agreed_fee > 0, Deal.completed_at.is_not(None), await shared_deals(db)))).scalars().all()
        if deals:
            names = dict((await db.execute(select(Club.id, Club.name).where(
                Club.id.in_({c for d in deals for c in (d.buyer_club_id, d.seller_club_id) if c}))) ).all())
            for d in deals:
                offer(d.player_id, {"fee_gbp": round(float(d.agreed_fee)), "fee_display": None,
                                    "date": _day(d.completed_at), "from": names.get(d.seller_club_id),
                                    "to": names.get(d.buyer_club_id), "source": "TransferX",
                                    "source_key": "TRANSFERX", "basis": "PERMANENT"})
    for pid, row in best.items():
        later = [d for d in free_dates.get(pid, []) if (d - row["date"]).days > 60]
        row["later_free_move"] = max(later).isoformat() if later else None
    return {pid: {**row, "date": row["date"].isoformat()} for pid, row in best.items()}
