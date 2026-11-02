"""A player's last transfer fee: what a club actually paid for him last time.

Shown next to the model's value wherever a price is (team feedback,
2026-10-29: "people will recognise true real-life valuations"). The newest
permanent move with a known fee wins:
- API-Football's transfer history (player_transfers), whose fee is a string
  such as "€ 116.6M", converted to pounds at the valuation model's rates;
- a completed TransferX deal, unless it's a demo or test transfer.
Loans, free transfers and moves with no fee on record don't count: they say
nothing about his price.
"""
from __future__ import annotations

import re
import uuid
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

_FEE_RE = re.compile(r"(?P<cur>€|£|\$|&pound;|&euro;)?\s*(?P<num>\d+(?:[.,]\d+)?)\s*(?P<unit>mln|[MmKkBb])?", re.I)
_UNIT = {"m": 1e6, "mln": 1e6, "k": 1e3, "b": 1e9}


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


async def last_transfer_fees(db: AsyncSession, player_ids) -> dict[uuid.UUID, dict]:
    """{player_id: {"fee_gbp", "fee_display", "date", "from", "to", "source"}}
    for the players with a known last fee; the rest are absent."""
    from app.clubs.models import Club
    from app.deals.models import Deal, DealStatus, DealType
    from app.demo.service import shared_deals
    from app.players.models import PlayerTransfer

    ids = list(player_ids)
    if not ids:
        return {}
    best: dict[uuid.UUID, dict] = {}

    def offer(pid, row):
        if row["date"] is None:
            return
        if pid not in best or row["date"] > best[pid]["date"]:
            best[pid] = row

    for t in (await db.execute(select(PlayerTransfer).where(
            PlayerTransfer.player_id.in_(ids), PlayerTransfer.fee_display.is_not(None),
            PlayerTransfer.transfer_date.is_not(None)))).scalars():
        if (t.transfer_type or "").lower() == "loan":
            continue
        gbp = fee_gbp(t.fee_display)
        if gbp:
            offer(t.player_id, {"fee_gbp": round(gbp), "fee_display": t.fee_display, "date": t.transfer_date,
                                "from": t.team_out_name, "to": t.team_in_name, "source": "API-Football"})

    deals = (await db.execute(select(Deal).where(
        Deal.player_id.in_(ids), Deal.status == DealStatus.COMPLETED, Deal.deal_type == DealType.PERMANENT,
        Deal.agreed_fee > 0, Deal.completed_at.is_not(None), await shared_deals(db)))).scalars().all()
    if deals:
        names = dict((await db.execute(select(Club.id, Club.name).where(
            Club.id.in_({c for d in deals for c in (d.buyer_club_id, d.seller_club_id) if c}))) ).all())
        for d in deals:
            offer(d.player_id, {"fee_gbp": round(float(d.agreed_fee)), "fee_display": None,
                                "date": _day(d.completed_at), "from": names.get(d.seller_club_id),
                                "to": names.get(d.buyer_club_id), "source": "TransferX"})
    return {pid: {**row, "date": row["date"].isoformat()} for pid, row in best.items()}
