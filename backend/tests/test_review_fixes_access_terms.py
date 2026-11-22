"""Fixes from the code review of 17 November 2026
(docs/reviews/2026-11-17-code-review-fix-spec.md), items 1, 2, 8 and 15."""
import uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from starlette.requests import Request

from tests.conftest import _auth_headers, _register
from tests.test_deals import _create_deal_via_offer, _get_finance

pytestmark = pytest.mark.asyncio


async def _staff(client, db, email: str) -> dict:
    from app.auth.models import User

    tokens = await _register(client, email, club_name="Staff FC")
    (await db.execute(select(User).where(User.email == email))).scalar_one().is_superuser = True
    await db.commit()
    return tokens


async def _agent(client) -> dict:
    r = await client.post("/auth/register", json={
        "email": f"agent-{uuid.uuid4().hex[:6]}@review.com", "password": "password123", "user_type": "AGENT",
        "display_name": "Review Agent", "agency_name": "Review Agency", "country": "England"})
    assert r.status_code == 201, r.text
    return r.json()


# ── Item 1: only staff write player stats, form, snapshots, sync state, leagues ──


def _writes(player_id: str) -> list[tuple[str, str, dict]]:
    return [
        ("PUT", f"/players/{player_id}/stats", {"vendor": "api-football", "league_id": "39", "season": "2024/25"}),
        ("PUT", f"/players/{player_id}/form", {"form_score": "8.0", "games_considered": 5}),
        ("POST", f"/players/{player_id}/snapshots", {"vendor": "api-football", "payload": {}}),
        ("PUT", "/stats/sync-states/api-football", {"success": True}),
        ("POST", "/world/leagues", {"vendor": "api-football", "league_id": "39", "name": "Premier League"}),
        ("POST", f"/vendor/sync/players/{player_id}", {}),
    ]


async def test_only_staff_can_write_player_data(client: AsyncClient, db):
    club = await _register(client, "club@review.com", club_name="Review FC")
    agent = await _agent(client)
    staff = await _staff(client, db, "staff@review.com")
    r = await client.post("/players", json={"name": "Review Player", "position": "MID"}, headers=_auth_headers(club))
    player_id = r.json()["id"]

    for method, url, body in _writes(player_id):
        for who in (club, agent):
            r = await client.request(method, url, json=body, headers=_auth_headers(who))
            assert r.status_code == 403, (method, url, r.status_code, r.text)
    # Staff get past the check (the vendor sync then fails for want of a vendor id).
    for method, url, body in _writes(player_id):
        r = await client.request(method, url, json=body, headers=_auth_headers(staff))
        assert r.status_code != 403, (method, url, r.text)
        assert r.status_code in (200, 201) or url.startswith("/vendor/sync/"), (method, url, r.text)


# ── Item 2: no claiming a real club from the world-team directory ────────────


async def test_an_agent_cannot_claim_a_world_team_as_its_club(client: AsyncClient, db):
    from app.clubs.models import Club
    from app.world.models import WorldTeam

    team = WorldTeam(vendor="api-football", vendor_id="42", name="Arsenal", country="England")
    db.add(team)
    await db.commit()
    agent = await _agent(client)

    r = await client.post(f"/clubs/from-world-team/{team.id}", headers=_auth_headers(agent))
    assert r.status_code in (404, 405)
    assert (await db.execute(select(Club).where(Club.name == "Arsenal"))).scalar_one_or_none() is None


# ── Item 8: the client's address behind a proxy ──────────────────────────────


def _request(xff: list[str], peer: str = "10.0.0.1") -> Request:
    headers = [(b"x-forwarded-for", v.encode()) for v in xff]
    return Request({"type": "http", "headers": headers, "client": (peer, 1234)})


def test_the_client_address_is_the_one_the_proxy_appended():
    from app.common.client_ip import client_ip

    # A forged entry to the left of the proxy's is ignored.
    assert client_ip(_request(["6.6.6.6, 81.2.69.160"]), hops=1) == "81.2.69.160"
    assert client_ip(_request(["6.6.6.6", "81.2.69.160"]), hops=1) == "81.2.69.160"
    assert client_ip(_request(["81.2.69.160"]), hops=1) == "81.2.69.160"
    # No proxy in front (local): the header is the client's own and isn't believed.
    assert client_ip(_request(["6.6.6.6"]), hops=0) == "10.0.0.1"
    assert client_ip(_request([]), hops=1) == "10.0.0.1"


def test_the_limiters_forget_idle_callers():
    from app.ai import rate_limit
    from app.monitoring import router as monitoring

    rate_limit._windows.clear()
    rate_limit._swept = 0.0
    rate_limit._windows["old"].append(0.0)
    rate_limit._sweep(10_000.0)
    assert "old" not in rate_limit._windows
    rate_limit.get_rate_limit_status(uuid.uuid4())
    assert len(rate_limit._windows) == 0, "a status read doesn't add a key"

    monitoring._client_hits.clear()
    monitoring._client_hits_swept = 0.0
    monitoring._client_hits.update({"old": [0.0], "new": [9_990.0]})
    monitoring._sweep_client_hits(10_000.0)
    assert list(monitoring._client_hits) == ["new"]


# ── Item 15: personal terms values ──────────────────────────────────────────


@pytest.fixture
async def terms_deal(client: AsyncClient, db):
    buyer = await _register(client, "buyer@review.com", club_name="Buyer FC")
    seller = await _register(client, "seller@review.com", club_name="Seller FC")
    deal = await _create_deal_via_offer(client, buyer, seller, db, wage_weekly=80_000)
    r = await client.post(f"/deals/{deal['id']}/advance", headers=_auth_headers(buyer))
    assert r.json()["stage"] == "PERSONAL_TERMS", r.text
    return deal, buyer


@pytest.mark.parametrize("terms", [
    {"wage_weekly": -500000, "length_years": 4},
    {"wage_weekly": 0, "length_years": 4},
    {"wage_weekly": 50000, "signing_bonus": -1, "length_years": 4},
    {"wage_weekly": 50000, "length_years": 0},
    {"wage_weekly": 50000, "length_years": 10},
])
async def test_out_of_range_terms_are_refused(client: AsyncClient, terms_deal, terms):
    deal, buyer = terms_deal
    r = await client.put(f"/deals/{deal['id']}/personal-terms", json=terms, headers=_auth_headers(buyer))
    assert r.status_code == 422, r.text


async def test_the_service_refuses_them_too():
    from app.deals.service import check_terms_values

    for args in ((Decimal(-1), None, 4), (Decimal(1000), Decimal(-1), 4), (Decimal(1000), None, 6)):
        with pytest.raises(ValueError):
            check_terms_values(*args)
    check_terms_values(Decimal(1000), Decimal(0), 5)


async def test_a_lower_agreed_wage_releases_only_the_difference(client: AsyncClient, db, terms_deal):
    deal, buyer = terms_deal
    before = await _get_finance(client, _auth_headers(buyer))
    r = await client.put(f"/deals/{deal['id']}/personal-terms", headers=_auth_headers(buyer),
                         json={"wage_weekly": 50000, "length_years": 4})
    assert r.status_code == 200, r.text
    staff = await _staff(client, db, "consent-staff@review.com")
    r = await client.post(f"/deals/{deal['id']}/personal-terms/player-consent",
                          json={"agreement": "AGREED"}, headers=_auth_headers(staff))
    assert r.status_code == 200, r.text
    r = await client.post(f"/deals/{deal['id']}/advance", headers=_auth_headers(buyer))
    assert r.status_code == 200, r.text

    after = await _get_finance(client, _auth_headers(buyer))
    assert Decimal(before["wage_committed_weekly"]) - Decimal(after["wage_committed_weekly"]) == Decimal(30000)
