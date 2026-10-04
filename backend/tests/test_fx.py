"""Display-only exchange rates: £1 in EUR and USD from the ECB file."""
import pytest
from httpx import AsyncClient

from app.fx import service

ECB = """<?xml version="1.0" encoding="UTF-8"?>
<gesmes:Envelope xmlns:gesmes="http://www.gesmes.org/xml/2002-08-01" xmlns="http://www.ecb.int/vocabulary/2002-08-01/eurofxref">
  <Cube><Cube time="2026-10-02">
    <Cube currency="USD" rate="1.1000"/><Cube currency="GBP" rate="0.8500"/>
  </Cube></Cube>
</gesmes:Envelope>"""


def test_parse_ecb_turns_euro_rates_into_pound_rates():
    rates, as_of = service.parse_ecb(ECB)
    assert as_of == "2026-10-02"
    assert rates == {"EUR": round(1 / 0.85, 4), "USD": round(1.1 / 0.85, 4)}


@pytest.mark.asyncio
async def test_without_a_source_the_fallback_rates_are_labelled(client: AsyncClient, monkeypatch):
    monkeypatch.setattr(service, "_cache", {})
    body = (await client.get("/fx/rates")).json()
    assert body["base"] == "GBP" and body["source"] == "fallback" and body["as_of"] is None
    assert set(body["rates"]) == {"EUR", "USD"}
