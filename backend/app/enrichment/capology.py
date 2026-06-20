"""Capology wage data adapter (TRA-67).

Fetches salary/contract data from the Capology API using the player's capology_slug.
Requires:
  CAPOLOGY_API_KEY  — API key for Capology (required; returns None when unset)
  CAPOLOGY_BASE_URL — override for testing (default: https://api.capology.com/v1)
"""
import logging
import os
from datetime import date
from decimal import Decimal

import httpx

from app.enrichment.protocols import ContractResult
from app.players.models import WageSource

logger = logging.getLogger(__name__)

_DEFAULT_BASE_URL = "https://api.capology.com/v1"


class CapologyAdapter:
    def __init__(self) -> None:
        self._api_key = os.getenv("CAPOLOGY_API_KEY", "")
        self._base_url = os.getenv("CAPOLOGY_BASE_URL", _DEFAULT_BASE_URL).rstrip("/")

    async def get_contract(self, external_id: str) -> ContractResult | None:
        if not self._api_key:
            logger.debug("CAPOLOGY_API_KEY not set — skipping Capology lookup for slug %s", external_id)
            return None

        url = f"{self._base_url}/players/{external_id}/salary"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url, headers={"Authorization": f"Bearer {self._api_key}"})
                resp.raise_for_status()
                data = resp.json()

            wage_raw = data.get("weekly_gross")
            wage_weekly = Decimal(str(wage_raw)) if wage_raw is not None else None
            currency = data.get("currency", "GBP")

            expiry_raw = data.get("contract_expiry")
            contract_expiry = date.fromisoformat(expiry_raw) if expiry_raw else None

            signed_raw = data.get("contract_signed")
            contract_signed = date.fromisoformat(signed_raw) if signed_raw else None

            return ContractResult(
                contract_expiry=contract_expiry,
                contract_signed=contract_signed,
                wage_weekly=wage_weekly,
                wage_currency=currency,
                wage_verified=True,
                source=WageSource.CAPOLOGY,
            )

        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                logger.info("Capology: player slug %s not found", external_id)
                return None
            logger.warning("Capology API error for slug %s: %s", external_id, exc)
            return None
        except Exception:
            logger.exception("Unexpected error fetching Capology data for slug %s", external_id)
            return None
