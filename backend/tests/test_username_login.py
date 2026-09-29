"""Signing in with a username: the part of the email before the "@"."""

import pytest
from httpx import AsyncClient

from tests.conftest import _register


async def _login(client: AsyncClient, identifier: str, password: str = "password123"):
    return await client.post("/auth/login", json={"email": identifier, "password": password})


@pytest.mark.asyncio
async def test_username_signs_in(client: AsyncClient):
    await _register(client, "astonvilla@clubs-example.com", club_name="Aston Villa")
    resp = await _login(client, "astonvilla")
    assert resp.status_code == 200, resp.text
    me = await client.get("/auth/me", headers={"Authorization": f"Bearer {resp.json()['access_token']}"})
    assert me.json()["email"] == "astonvilla@clubs-example.com"


@pytest.mark.asyncio
async def test_username_and_email_ignore_case(client: AsyncClient):
    await _register(client, "westham@clubs-example.com", club_name="West Ham")
    assert (await _login(client, "WestHam")).status_code == 200
    assert (await _login(client, "  westham ")).status_code == 200
    assert (await _login(client, "WESTHAM@CLUBS-EXAMPLE.COM")).status_code == 200


@pytest.mark.asyncio
async def test_wrong_password_is_refused(client: AsyncClient):
    await _register(client, "fulham@clubs-example.com", club_name="Fulham")
    resp = await _login(client, "fulham", password="not-the-password")
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Incorrect email, username or password"


@pytest.mark.asyncio
async def test_unknown_username_is_refused(client: AsyncClient):
    assert (await _login(client, "nobody")).status_code == 401


@pytest.mark.asyncio
async def test_a_shared_username_asks_for_the_email(client: AsyncClient):
    await _register(client, "owner@first-example.com", club_name="First FC")
    await _register(client, "owner@second-example.com", club_name="Second FC")
    resp = await _login(client, "owner")
    assert resp.status_code == 401
    assert "email address" in resp.json()["detail"]
    assert (await _login(client, "owner@second-example.com")).status_code == 200


@pytest.mark.asyncio
async def test_like_wildcards_in_a_username_are_literal(client: AsyncClient):
    await _register(client, "a_b@clubs-example.com", club_name="Underscore FC")
    assert (await _login(client, "axb")).status_code == 401  # "_" is not a wildcard
    assert (await _login(client, "a%")).status_code == 401
    assert (await _login(client, "a_b")).status_code == 200
