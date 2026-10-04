"""Settings by tier: one switch sets a channel for every type in the tier."""
import pytest
from httpx import AsyncClient

from tests.conftest import _auth_headers, _register

pytestmark = pytest.mark.asyncio


async def test_a_tier_switch_sets_every_type_in_it_but_not_the_daily_summary(client: AsyncClient):
    h = _auth_headers(await _register(client, "tier_prefs@test.com", club_name="Tier FC"))
    resp = await client.patch("/notifications/preferences/tier/FYI", json={"email_enabled": False}, headers=h)
    assert resp.status_code == 200, resp.text
    prefs = {p["type"]: p for p in resp.json()["preferences"]}
    fyi = [p for p in prefs.values() if p["tier"] == "FYI" and p["type"] != "DAILY_DIGEST"]
    assert fyi and all(not p["email_enabled"] for p in fyi)
    assert prefs["DAILY_DIGEST"]["email_enabled"] is True
    assert prefs["OFFER_RECEIVED"]["email_enabled"] is True  # another tier, untouched

    resp = await client.patch("/notifications/preferences/tier/YOUR_MOVE", json={"push_enabled": False}, headers=h)
    assert all(not p["push_enabled"] for p in resp.json()["preferences"] if p["tier"] == "YOUR_MOVE")
    assert (await client.patch("/notifications/preferences/tier/NOPE", json={"enabled": False}, headers=h)).status_code == 400
