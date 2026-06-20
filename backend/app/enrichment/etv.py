"""ETV (European Transfer Value) valuation provider adapter (TRA-67).

Fetches market value data from the ETV API using the player's etv_player_id.
Requires:
  ETV_API_KEY  — API key for ETV (required; adapter returns None when unset)
  ETV_BASE_URL — override for testing (default: https://api.etv.football/v1)
"""
import logging
import os
from datetime import date, datetime
from decimal import Decimal

import httpx

from app.enrichment.protocols import ValuationResult
from app.players.models import ValuationSource

logger = logging.getLogger(__name__)

_DEFAULT_BASE_URL = "https://api.etv.football/v1"


class ETVAdapter:
    def __init__(self) -> None:
        self._api_key = os.getenv("ETV_API_KEY", "")
        self._base_url = os.getenv("ETV_BASE_URL", _DEFAULT_BASE_URL).rstrip("/")

    async def get_valuation(self, external_id: str) -> ValuationResult | None:
        if not self._api_key:
            logger.debug("ETV_API_KEY not set — skipping ETV lookup for player %s", external_id)
            return None

        url = f"{self._base_url}/players/{external_id}/valuation"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url, headers={"X-API-Key": self._api_key})
                resp.raise_for_status()
                data = resp.json()

            market_value = Decimal(str(data["market_value"]))
            currency = data.get("currency", "EUR")
            low = Decimal(str(data["range_low"])) if data.get("range_low") is not None else None
            high = Decimal(str(data["range_high"])) if data.get("range_high") is not None else None
            as_of_raw = data.get("as_of", datetime.utcnow().strftime("%Y-%m-%d"))
            as_of = date.fromisoformat(as_of_raw)

            return ValuationResult(
                market_value=market_value,
                market_value_currency=currency,
                valuation_low=low,
                valuation_high=high,
                source=ValuationSource.ETV,
                as_of=as_of,
            )

        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                logger.info("ETV: player %s not found", external_id)
                return None
            logger.warning("ETV API error for player %s: %s", external_id, exc)
            return None
        except Exception:
            logger.exception("Unexpected error fetching ETV valuation for player %s", external_id)
            return None
