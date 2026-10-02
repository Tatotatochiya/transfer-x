"""Lite mode preferences (docs/feature_spec/lite-mode, BACKEND.md §1)."""

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.config import settings
from tests.conftest import _auth_headers, _register


async def _prefs(client, tokens):
    return (await client.get("/users/me/preferences", headers=_auth_headers(tokens))).json()


@pytest.fixture
def role_default_on(monkeypatch):
    monkeypatch.setattr(settings, "lite_role_default_on", True)


@pytest.mark.asyncio
async def test_off_for_everyone_while_the_role_default_is_off(client: AsyncClient):
    owner = await _register(client, "owner_lite@clubs-example.com", club_name="Lite FC")
    prefs = await _prefs(client, owner)
    lite = {k: prefs[k] for k in ("lite_mode", "lite_mode_is_default", "text_scale")}
    assert lite == {"lite_mode": False, "lite_mode_is_default": True, "text_scale": "NORMAL"}


@pytest.mark.asyncio
async def test_role_default_is_on_for_an_owner_not_an_agent(client: AsyncClient, role_default_on):
    owner = await _register(client, "owner_lite@clubs-example.com", club_name="Lite FC")
    assert (await _prefs(client, owner))["lite_mode"] is True

    agent = (await client.post("/auth/register", json={
        "email": "agent_lite@clubs-example.com", "password": "password123", "user_type": "AGENT",
        "display_name": "Lite Agent", "agency_name": "Lite Sports", "country": "England",
    })).json()
    assert (await _prefs(client, agent))["lite_mode"] is False


@pytest.mark.asyncio
async def test_choosing_overrides_the_default_and_is_audited_once(client: AsyncClient, db, role_default_on):
    from app.audit.models import AuditEvent

    owner = await _register(client, "owner_lite@clubs-example.com", club_name="Lite FC")
    resp = await client.patch("/users/me/preferences", json={"lite_mode": False}, headers=_auth_headers(owner))
    assert resp.status_code == 200, resp.text
    assert resp.json()["lite_mode"] is False and resp.json()["lite_mode_is_default"] is False

    # Setting the same value again is not a change, so no second audit event.
    await client.patch("/users/me/preferences", json={"lite_mode": False}, headers=_auth_headers(owner))
    events = (await db.execute(select(AuditEvent).where(AuditEvent.action == "lite_mode_changed"))).scalars().all()
    assert len(events) == 1 and events[0].payload_json["lite_mode"] is False


@pytest.mark.asyncio
async def test_text_scale_persists(client: AsyncClient):
    owner = await _register(client, "owner_lite@clubs-example.com", club_name="Lite FC")
    resp = await client.patch("/users/me/preferences", json={"text_scale": "LARGER"}, headers=_auth_headers(owner))
    assert resp.json()["text_scale"] == "LARGER"
    assert (await _prefs(client, owner))["text_scale"] == "LARGER"
    # Changing only the text scale leaves Lite mode on its default.
    assert (await _prefs(client, owner))["lite_mode_is_default"] is True


@pytest.mark.asyncio
async def test_bad_value_and_no_auth_are_refused(client: AsyncClient):
    owner = await _register(client, "owner_lite@clubs-example.com", club_name="Lite FC")
    assert (await client.patch(
        "/users/me/preferences", json={"text_scale": "HUGE"}, headers=_auth_headers(owner)
    )).status_code == 422
    assert (await client.get("/users/me/preferences")).status_code == 401
