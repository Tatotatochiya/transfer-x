"""Transfermarkt scrape adapter — PROTOTYPE ONLY, not for production.

Guarded via registry.py: ENRICHMENT_VALUATION_SOURCE=TRANSFERMARKT is rejected
at import time when APP_ENV=production (ToS violation, no redistribution rights).

Uses the unofficial JSON API endpoint scraped from Transfermarkt's web app.
Player external ID is the Transfermarkt numeric ID (e.g. "258923" for Lewandowski).
"""
import logging
import os
from datetime import date
from decimal import Decimal

import httpx

from app.enrichment.protocols import ValuationResult
from app.players.models import ValuationSource

logger = logging.getLogger(__name__)

_DEFAULT_BASE_URL = "https://www.transfermarkt.co.uk"
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (TransferX prototype enrichment; dev only)",
}


class TransfermarktAdapter:
    """Scrape adapter for Transfermarkt — prototype use only."""

    def __init__(self) -> None:
        self._base_url = os.getenv("TRANSFERMARKT_BASE_URL", _DEFAULT_BASE_URL).rstrip("/")

    async def get_valuation(self, external_id: str) -> ValuationResult | None:
        url = f"{self._base_url}/ceapi/marketValueDevelopment/graph/{external_id}"
        try:
            async with httpx.AsyncClient(timeout=15.0, headers=_HEADERS, follow_redirects=True) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                data = resp.json()

            # Response: {"list": [{"datum_mw": "Jan 1, 2024", "mw": "€30.00m", ...}], "current": ...}
            current_raw: str = data.get("current", "")
            market_value = _parse_tm_value(current_raw)
            if market_value is None:
                return None

            entries = data.get("list", [])
            as_of = date.today()
            if entries:
                last = entries[-1]
                try:
                    as_of = date.fromisoformat(last.get("datum_mw", "")[:10])
                except ValueError:
                    pass

            return ValuationResult(
                market_value=market_value,
                market_value_currency="EUR",
                valuation_low=None,
                valuation_high=None,
                source=ValuationSource.TRANSFERMARKT,
                as_of=as_of,
            )

        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in (404, 403):
                logger.info("Transfermarkt: player %s not found or blocked", external_id)
                return None
            logger.warning("Transfermarkt error for player %s: %s", external_id, exc)
            return None
        except Exception:
            logger.exception("Unexpected error scraping Transfermarkt for player %s", external_id)
            return None


def _parse_tm_value(raw: str) -> Decimal | None:
    """Parse Transfermarkt value strings like '€30.00m', '€500k'."""
    raw = raw.strip().lower().replace("€", "").replace(",", "").replace(" ", "")
    try:
        if raw.endswith("m"):
            return Decimal(str(float(raw[:-1]) * 1_000_000))
        if raw.endswith("k"):
            return Decimal(str(float(raw[:-1]) * 1_000))
        return Decimal(raw) if raw else None
    except Exception:
        return None
