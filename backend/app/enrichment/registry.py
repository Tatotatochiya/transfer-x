"""Config-driven provider selection (TRA-66).

Active provider is read from environment variables:
  ENRICHMENT_VALUATION_SOURCE  — "ETV" | "MANUAL"  (default: MANUAL)
  ENRICHMENT_WAGE_SOURCE       — "CAPOLOGY" | "ESTIMATED" | "MANUAL"  (default: MANUAL)

TRANSFERMARKT is a prototype-only source (scraped, no redistribution rights, no SLA).
It is accepted in development but raises at import time if selected in production.
"""
import os


def get_active_valuation_source() -> str:
    source = os.getenv("ENRICHMENT_VALUATION_SOURCE", "MANUAL").upper()
    _guard_transfermarkt(source)
    return source


def get_active_wage_source() -> str:
    return os.getenv("ENRICHMENT_WAGE_SOURCE", "MANUAL").upper()


def _guard_transfermarkt(source: str) -> None:
    if source == "TRANSFERMARKT" and os.getenv("APP_ENV", "development").lower() == "production":
        raise RuntimeError(
            "ENRICHMENT_VALUATION_SOURCE=TRANSFERMARKT is prototype-only and must not be used "
            "in production: no redistribution rights, no SLA, ToS violation. "
            "Set ENRICHMENT_VALUATION_SOURCE=ETV for production."
        )
