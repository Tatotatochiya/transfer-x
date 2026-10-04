"""Signed-in devices (Phase 1): each sign-in is a session that survives
token refreshes, can be listed, and can be signed out from elsewhere."""
import pytest
from httpx import AsyncClient

from tests.conftest import _register

pytestmark = pytest.mark.asyncio
PHONE = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_4 like Mac OS X) AppleWebKit/605.1.15 Version/18.4 Mobile/15E148 Safari/604.1"
MAC = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/129.0 Safari/537.36"


async def _login(client, ua):
    resp = await client.post("/auth/login", json={"email": "devices@test.com", "password": "password123"},
                             headers={"User-Agent": ua})
    assert resp.status_code == 200, resp.text
    return resp.json()


def _h(tokens):
    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def test_devices_are_listed_survive_refresh_and_can_be_signed_out(client: AsyncClient):
    await _register(client, "devices@test.com", club_name="Devices FC")
    mac = await _login(client, MAC)
    phone = await _login(client, PHONE)

    sessions = (await client.get("/auth/sessions", headers=_h(mac))).json()
    mine = [s for s in sessions if s["current"]]
    assert len(mine) == 1 and mine[0]["device"] == "Chrome on Mac"
    assert "Safari on iPhone" in [s["device"] for s in sessions]

    # A refresh keeps the same session (same id), with a new token.
    refreshed = (await client.post("/auth/refresh", json={"refresh_token": phone["refresh_token"]},
                                   headers={"User-Agent": PHONE})).json()
    phone_id = next(s["id"] for s in sessions if s["device"] == "Safari on iPhone")
    after = (await client.get("/auth/sessions", headers=_h(refreshed))).json()
    assert next(s for s in after if s["current"])["id"] == phone_id

    # Sign the phone out from the Mac: its access token stops working at once,
    # and its refresh token is gone.
    assert (await client.delete(f"/auth/sessions/{phone_id}", headers=_h(mac))).status_code == 204
    assert (await client.get("/auth/me", headers=_h(refreshed))).status_code == 401
    assert (await client.post("/auth/refresh", json={"refresh_token": refreshed["refresh_token"]})).status_code == 401
    assert (await client.get("/auth/me", headers=_h(mac))).status_code == 200


async def test_sign_out_everywhere_else_keeps_this_device(client: AsyncClient):
    await _register(client, "devices@test.com", club_name="Devices FC")
    here = await _login(client, MAC)
    others = [await _login(client, PHONE) for _ in range(2)]
    resp = await client.post("/auth/sessions/sign-out-others", headers=_h(here))
    assert resp.status_code == 200 and resp.json()["signed_out"] >= 2
    for t in others:
        assert (await client.get("/auth/me", headers=_h(t))).status_code == 401
    assert (await client.get("/auth/me", headers=_h(here))).status_code == 200
    assert [s["current"] for s in (await client.get("/auth/sessions", headers=_h(here))).json()] == [True]
