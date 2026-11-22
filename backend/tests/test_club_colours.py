"""A club's own colours for its Dashboard band (feature_spec/club-dashboard §3.1)."""
import pytest
from httpx import AsyncClient

from tests.conftest import _auth_headers, _register
from tests.test_capabilities import _create_staff

pytestmark = pytest.mark.asyncio


async def _owner(client) -> dict:
    return _auth_headers(await _register(client, "colours_owner@test.com", club_name="Colour FC"))


async def test_an_admin_sets_both_colours_in_upper_case(client: AsyncClient):
    h = await _owner(client)
    r = await client.patch("/clubs/me", json={"brand_primary": "#db0007", "brand_secondary": "#FFFFFF"}, headers=h)
    assert r.status_code == 200, r.text
    assert (r.json()["brand_primary"], r.json()["brand_secondary"]) == ("#DB0007", "#FFFFFF")
    me = (await client.get("/clubs/me", headers=h)).json()
    assert (me["brand_primary"], me["brand_secondary"]) == ("#DB0007", "#FFFFFF")


async def test_an_empty_string_clears_a_colour_and_none_leaves_it(client: AsyncClient):
    h = await _owner(client)
    await client.patch("/clubs/me", json={"brand_primary": "#DB0007", "brand_secondary": "#FFFFFF"}, headers=h)
    r = await client.patch("/clubs/me", json={"brand_primary": ""}, headers=h)
    assert (r.json()["brand_primary"], r.json()["brand_secondary"]) == (None, "#FFFFFF")
    r = await client.patch("/clubs/me", json={"city": "London"}, headers=h)
    assert r.json()["brand_secondary"] == "#FFFFFF"


@pytest.mark.parametrize("bad", ["red", "#FFF", "DB0007", "#GG0000", "#DB00071"])
async def test_anything_but_a_six_digit_hex_is_refused(client: AsyncClient, bad):
    h = await _owner(client)
    r = await client.patch("/clubs/me", json={"brand_primary": bad}, headers=h)
    assert r.status_code == 422
    assert "Use a colour like #DB0007" in r.text


async def test_a_scout_cannot_set_them(client: AsyncClient, db):
    h = await _owner(client)
    scout = await _create_staff(client, db, h, "colours_scout@test.com", "SCOUT")
    r = await client.patch("/clubs/me", json={"brand_primary": "#DB0007"}, headers=_auth_headers(scout))
    assert r.status_code == 403


async def test_other_clubs_never_see_them(client: AsyncClient):
    h = await _owner(client)
    await client.patch("/clubs/me", json={"brand_primary": "#DB0007"}, headers=h)
    club_id = (await client.get("/clubs/me", headers=h)).json()["id"]
    other = _auth_headers(await _register(client, "colours_other@test.com", club_name="Other FC"))
    seen = (await client.get(f"/clubs/{club_id}", headers=other)).json()
    assert "brand_primary" not in seen and "brand_secondary" not in seen
    listed = (await client.get("/clubs", params={"search": "Colour"}, headers=other)).text
    assert "DB0007" not in listed
