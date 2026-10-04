"""Exchange rates for display estimates only.

Every amount in TransferX is stored and agreed in pounds. A club that picks
EUR or USD sees "≈ €21.0m" next to the bigger £ figures; nothing it types or
agrees to is converted. Rates are the ECB's daily reference rates, fetched at
most twice a day and kept in memory. If the ECB can't be reached, the last
good rates are kept, or fixed fallback rates are used, and the response says
which.
"""
import logging
import time
import xml.etree.ElementTree as ET
from datetime import date

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

CURRENCIES = ("EUR", "USD")
# Roughly right, for when the ECB has never answered. Labelled "fallback".
FALLBACK = {"EUR": 1.17, "USD": 1.33}
REFRESH_SECONDS = 12 * 3600
RETRY_SECONDS = 15 * 60

_cache: dict = {}  # {"rates", "as_of", "source", "fetched_at"}


def parse_ecb(xml_text: str) -> tuple[dict[str, float], str]:
    """£1 in each currency, from the ECB's euro-based daily file."""
    root = ET.fromstring(xml_text)
    per_eur: dict[str, float] = {}
    as_of = None
    for el in root.iter():
        if el.tag.endswith("Cube") and "time" in el.attrib:
            as_of = el.attrib["time"]
        if el.tag.endswith("Cube") and "currency" in el.attrib:
            per_eur[el.attrib["currency"]] = float(el.attrib["rate"])
    gbp = per_eur["GBP"]
    rates = {"EUR": round(1 / gbp, 4), "USD": round(per_eur["USD"] / gbp, 4)}
    return rates, as_of or date.today().isoformat()


async def get_rates() -> dict:
    now = time.monotonic()
    fresh = _cache and now - _cache["fetched_at"] < (
        REFRESH_SECONDS if _cache["source"] == "ECB" else RETRY_SECONDS
    )
    if fresh:
        return _public(_cache)
    if settings.fx_rates_url:
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get(settings.fx_rates_url)
                resp.raise_for_status()
            rates, as_of = parse_ecb(resp.text)
            _cache.update(rates=rates, as_of=as_of, source="ECB", fetched_at=now)
            return _public(_cache)
        except Exception:
            logger.warning("Couldn't fetch exchange rates; using the last good or fallback rates", exc_info=True)
    if _cache.get("source") == "ECB":
        _cache["fetched_at"] = now - REFRESH_SECONDS + RETRY_SECONDS  # try again in 15 minutes
        return _public(_cache)
    _cache.update(rates=dict(FALLBACK), as_of=None, source="fallback", fetched_at=now)
    return _public(_cache)


def _public(c: dict) -> dict:
    return {"base": "GBP", "rates": c["rates"], "as_of": c["as_of"], "source": c["source"]}
