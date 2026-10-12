"""Real-world moves TransferX doesn't have yet (app/players/real_world.py)."""

import uuid
from datetime import date

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select

from tests.conftest import _auth_headers, _register
from tests.test_deals import _get_club_id

TODAY = date(2026, 10, 12)  # the 2026/27 season


@pytest_asyncio.fixture
async def clubs(client: AsyncClient, db) -> dict:
    """Two TransferX clubs, each matched to an API-Football team by its squad."""
    from app.world.models import WorldTeam

    out = {}
    for name, vendor in (("Bournemouth", "35"), ("Tottenham", "47")):
        tokens = await _register(client, f"{name.lower()}@rw-example.com", club_name=name)
        team = WorldTeam(vendor="api-football", vendor_id=vendor, name=name, crest_url=f"https://crest/{vendor}.png")
        db.add(team)
        await db.flush()
        out[name] = {"tokens": tokens, "id": uuid.UUID(await _get_club_id(client, _auth_headers(tokens))), "team": team}
    db.add(WorldTeam(vendor="api-football", vendor_id="2932", name="Al-Hilal Saudi FC"))
    await db.commit()
    return out


async def _contracted(db, club: dict, name: str, started=date(2024, 7, 1)):
    from app.players.models import Contract, Player, PlayerStatus

    p = Player(name=name, position="DEF", status=PlayerStatus.CONTRACTED, current_club_id=club["id"],
               world_team_id=club["team"].id)
    db.add(p)
    await db.flush()
    db.add(Contract(player_id=p.id, club_id=club["id"], is_active=True, start_date=started, end_date=date(2029, 6, 30)))
    await db.commit()
    return p


def _transfer(player, day, team_in, name_in, kind="Transfer", fee=None):
    from app.players.models import PlayerTransfer

    return PlayerTransfer(player_id=player.id, vendor="api-football", transfer_date=day, transfer_type=kind,
                          team_in_vendor_id=team_in, team_in_name=name_in, fee_display=fee)


def _played(player, team, name, *, season="2026", apps=3, last=None, fixture="1"):
    from app.stats.models import PlayerFixtureRating, PlayerStats

    rows = [PlayerStats(player_id=player.id, vendor="api-football", league_id="39", season=season,
                        team_vendor_id=team, team_name=name, appearances=apps, league_name="Premier League")]
    if last:
        rows.append(PlayerFixtureRating(player_id=player.id, fixture_vendor_id=fixture, fixture_date=last,
                                        team_vendor_id=team, minutes=90))
    return rows


async def _check(db, player):
    from app.players import real_world

    return (await real_world.check(db, [player], today=TODAY)).get(player.id)


@pytest.mark.asyncio
async def test_a_free_transfer_to_another_transferx_club_is_reported(db, clubs):
    senesi = await _contracted(db, clubs["Bournemouth"], "M. Senesi")
    db.add(_transfer(senesi, date(2026, 6, 30), "47", "Tottenham", fee="Free agent"))
    db.add_all(_played(senesi, "47", "Tottenham", last=date(2026, 9, 19)))
    await db.commit()

    move = await _check(db, senesi)
    assert move["kind"] == "transfer" and move["fee"] == "Free"
    assert (move["registered_club"], move["real_club"]) == ("Bournemouth", "Tottenham")
    assert move["real_club_on_transferx_id"] == str(clubs["Tottenham"]["id"])
    assert (move["moved_on"], move["last_played"]) == ("2026-06-30", "2026-09-19")
    assert move["real_club_logo"] == "https://crest/47.png"  # the stats row had none


@pytest.mark.asyncio
async def test_the_newest_evidence_wins(db, clubs):
    # Played for his club in August, then sold abroad where games aren't tracked.
    gone = await _contracted(db, clubs["Bournemouth"], "Gone Abroad")
    db.add_all(_played(gone, "35", "Bournemouth", last=date(2026, 8, 24)))
    db.add(_transfer(gone, date(2026, 9, 2), "2932", "Al-Hilal Saudi FC", fee="€ 40M"))
    # Joined last season, still playing for the club he's registered to.
    stayed = await _contracted(db, clubs["Bournemouth"], "Stayed Put", started=date(2025, 7, 1))
    db.add(_transfer(stayed, date(2025, 7, 1), "35", "Bournemouth"))
    db.add_all(_played(stayed, "35", "Bournemouth", last=date(2026, 9, 20), fixture="2"))
    await db.commit()

    move = await _check(db, gone)
    assert (move["kind"], move["real_club"], move["fee"]) == ("transfer", "Al-Hilal Saudi FC", "€ 40M")
    assert move["real_club_on_transferx_id"] is None
    assert await _check(db, stayed) is None


@pytest.mark.asyncio
async def test_loans_loan_returns_and_playing_without_a_transfer(db, clubs):
    loaned = await _contracted(db, clubs["Tottenham"], "Out On Loan")
    db.add(_transfer(loaned, date(2026, 8, 31), "35", "Bournemouth", kind="Loan"))
    back = await _contracted(db, clubs["Bournemouth"], "Loan Over")
    db.add(_transfer(back, date(2026, 6, 29), "2932", "Al-Hilal Saudi FC", fee="Return from loan"))
    seen = await _contracted(db, clubs["Bournemouth"], "Just Seen There")
    db.add_all(_played(seen, "47", "Tottenham", last=date(2026, 9, 13), fixture="3"))
    await db.commit()

    assert (await _check(db, loaned))["kind"] == "loan"
    returned = await _check(db, back)
    assert returned["kind"] == "loan_return" and returned["fee"] is None
    playing = await _check(db, seen)
    assert (playing["kind"], playing["moved_on"], playing["last_played"]) == ("playing", None, "2026-09-13")


@pytest.mark.asyncio
async def test_old_moves_youth_sides_and_internationals_are_not_moves(db, clubs):
    from app.players.models import Player

    youth = await _contracted(db, clubs["Bournemouth"], "Youth Side")
    db.add_all(_played(youth, "9035", "Bournemouth U21", last=date(2026, 9, 1), fixture="4"))
    old = await _contracted(db, clubs["Bournemouth"], "Old News")
    db.add(_transfer(old, date(2025, 1, 15), "47", "Tottenham"))  # last season, before his contract ended
    capped = await _contracted(db, clubs["Bournemouth"], "Capped")
    capped_row = await db.get(Player, capped.id)
    capped_row.nationality = "Argentina"
    db.add_all(_played(capped, "26", "Argentina", last=date(2026, 9, 9), fixture="5"))
    await db.commit()

    for p in (youth, old, capped):
        assert await _check(db, p) is None, p.name


@pytest.mark.asyncio
async def test_ledger_and_admin_list_report_it(client: AsyncClient, db, clubs):
    from app.auth.models import User

    senesi = await _contracted(db, clubs["Bournemouth"], "M. Senesi", started=date(2020, 7, 1))
    # The endpoints use today's season, so the move is dated today.
    db.add(_transfer(senesi, date.today(), "47", "Tottenham", fee="Free agent"))
    await db.commit()

    headers = _auth_headers(clubs["Tottenham"]["tokens"])
    ledger = (await client.get(f"/players/market/{senesi.id}/ledger", headers=headers)).json()
    assert ledger["real_world"]["real_club"] == "Tottenham"

    assert (await client.get("/admin/real-world-moves", headers=headers)).status_code == 403
    admin = await _register(client, "admin@rw-example.com", club_name="Admin FC")
    user = (await db.execute(select(User).where(User.email == "admin@rw-example.com"))).scalar_one()
    user.is_superuser = True
    await db.commit()
    got = (await client.get("/admin/real-world-moves", headers=_auth_headers(admin))).json()
    names = {m["name"]: m for m in got["mismatches"]}
    assert set(names) == {"M. Senesi"}
    assert got["counts"]["to_transferx_club"] == 1 and got["checked"] == 1


# ── Acting on a move: apply and dismiss (TransferX staff) ────────────────────


async def _admin(client, db) -> dict:
    from app.auth.models import User

    tokens = await _register(client, "staff@rw-example.com", club_name="Staff FC")
    user = (await db.execute(select(User).where(User.email == "staff@rw-example.com"))).scalar_one()
    user.is_superuser = True
    await db.commit()
    return tokens


async def _apply(client, admin, *players, reason="Matches the real-world transfer"):
    resp = await client.post("/admin/real-world-moves/apply", headers=_auth_headers(admin),
                             json={"player_ids": [str(p.id) for p in players], "reason": reason})
    assert resp.status_code == 200, resp.text
    return resp.json()


@pytest.mark.asyncio
async def test_apply_moves_him_to_the_transferx_club_and_closes_what_was_open(client: AsyncClient, db, clubs):
    from app.audit.models import AuditEvent
    from app.notifications.models import Notification, NotificationType
    from app.players.models import Contract, Player, PlayerStatus
    from tests.test_deals import _give_budget

    rival = await _register(client, "rival@rw-example.com", club_name="Rival FC")
    admin = await _admin(client, db)
    await _give_budget(db)
    senesi = await _contracted(db, clubs["Bournemouth"], "M. Senesi", started=date(2020, 7, 1))
    db.add(_transfer(senesi, date.today(), "47", "Tottenham", fee="Free agent"))
    await db.commit()
    offer = (await client.post("/offers", headers=_auth_headers(rival), json={
        "player_id": str(senesi.id), "to_club_id": str(clubs["Bournemouth"]["id"]), "fee_amount": 3_000_000,
    })).json()

    pid = senesi.id
    got = await _apply(client, admin, senesi)
    assert got["skipped"] == [] and got["applied"][0]["closed"]["offers"] == [offer["id"]]

    db.expire_all()
    player = await db.get(Player, pid)
    assert (player.current_club_id, player.status, player.team_name) == (clubs["Tottenham"]["id"], PlayerStatus.CONTRACTED, "Tottenham")
    contracts = {c.club_id: c for c in (await db.execute(select(Contract).where(Contract.player_id == pid))).scalars()}
    old, new = contracts[clubs["Bournemouth"]["id"]], contracts[clubs["Tottenham"]["id"]]
    assert (old.is_active, old.end_date) == (False, date.today())
    assert (new.is_active, new.start_date, new.confirmed_at) == (True, date.today(), None)  # for "Check your squad"
    assert (await client.get(f"/offers/{offer['id']}", headers=_auth_headers(rival))).json()["status"] == "WITHDRAWN"
    told = (await db.execute(select(Notification).where(
        Notification.type == NotificationType.REGISTRATION_UPDATED))).scalars().all()
    assert {n.message.split(":")[0] for n in told} >= {"TransferX staff took M. Senesi off your squad"}
    assert any("added M. Senesi to your squad" in n.message for n in told)
    event = (await db.execute(select(AuditEvent).where(AuditEvent.action == "admin.real_world_move.applied"))).scalar_one()
    assert event.payload_json["reason"] == "Matches the real-world transfer" and event.payload_json["to_club"] == "Tottenham"
    assert (await client.get("/admin/real-world-moves", headers=_auth_headers(admin))).json()["mismatches"] == []


@pytest.mark.asyncio
async def test_apply_to_a_club_outside_transferx_makes_him_external(client: AsyncClient, db, clubs):
    from app.players.models import Player, PlayerStatus
    from app.sales.models import Sale, SaleStatus

    admin = await _admin(client, db)
    gone = await _contracted(db, clubs["Bournemouth"], "Gone Abroad", started=date(2020, 7, 1))
    db.add(_transfer(gone, date.today(), "2932", "Al-Hilal Saudi FC", fee="€ 40M"))
    await db.commit()
    sale = await client.post("/sales", headers=_auth_headers(clubs["Bournemouth"]["tokens"]),
                             json={"player_id": str(gone.id), "sale_type": "OPEN_TO_OFFERS", "asking_price": 30_000_000})
    assert sale.status_code == 201, sale.text

    pid = gone.id
    got = await _apply(client, admin, gone)
    assert got["applied"][0]["closed"]["sales"] == [sale.json()["id"]]
    db.expire_all()
    player = await db.get(Player, pid)
    assert (player.current_club_id, player.status, player.team_name) == (None, PlayerStatus.EXTERNAL, "Al-Hilal Saudi FC")
    assert (await db.get(Sale, uuid.UUID(sale.json()["id"]))).status == SaleStatus.WITHDRAWN


@pytest.mark.asyncio
async def test_loans_and_players_in_a_deal_are_skipped_with_the_reason(client: AsyncClient, db, clubs):
    from tests.test_deals import _give_budget

    rival = await _register(client, "rival2@rw-example.com", club_name="Rival Two")
    admin = await _admin(client, db)
    await _give_budget(db)
    loaned = await _contracted(db, clubs["Tottenham"], "On Loan Abroad", started=date(2020, 7, 1))
    db.add(_transfer(loaned, date.today(), "2932", "Al-Hilal Saudi FC", kind="Loan"))
    busy = await _contracted(db, clubs["Bournemouth"], "Busy Bee", started=date(2020, 7, 1))
    db.add(_transfer(busy, date.today(), "47", "Tottenham"))
    moved = await _contracted(db, clubs["Bournemouth"], "Plain Move", started=date(2020, 7, 1))
    db.add(_transfer(moved, date.today(), "2932", "Al-Hilal Saudi FC"))
    await db.commit()
    offer = (await client.post("/offers", headers=_auth_headers(rival), json={
        "player_id": str(busy.id), "to_club_id": str(clubs["Bournemouth"]["id"]), "fee_amount": 2_000_000})).json()
    await client.post(f"/offers/{offer['id']}/accept", headers=_auth_headers(clubs["Bournemouth"]["tokens"]))

    listing = (await client.get("/admin/real-world-moves", headers=_auth_headers(admin))).json()
    blocked = {m["name"]: m["apply_blocked"] for m in listing["mismatches"]}
    assert "still Tottenham's player" in blocked["On Loan Abroad"]
    assert "in a deal on TransferX" in blocked["Busy Bee"]
    assert blocked["Plain Move"] is None

    got = await _apply(client, admin, loaned, busy, moved)
    assert [a["name"] for a in got["applied"]] == ["Plain Move"]  # the rest still go through
    assert {s["player_id"] for s in got["skipped"]} == {str(loaned.id), str(busy.id)}


@pytest.mark.asyncio
async def test_dismiss_stops_reporting_until_he_moves_somewhere_else(client: AsyncClient, db, clubs):
    from app.audit.models import AuditEvent

    admin = await _admin(client, db)
    from app.players import real_world

    loaned = await _contracted(db, clubs["Tottenham"], "On Loan Abroad", started=date(2020, 7, 1))
    went = real_world.season_start(real_world.current_season())  # earlier than the game below
    db.add(_transfer(loaned, went, "2932", "Al-Hilal Saudi FC", kind="Loan"))
    await db.commit()

    url = f"/admin/real-world-moves/{loaned.id}/dismiss"
    assert (await client.post(url, headers=_auth_headers(clubs["Tottenham"]["tokens"]), json={"reason": "Loan abroad"})).status_code == 403
    assert (await client.post(url, headers=_auth_headers(admin), json={"reason": "no"})).status_code == 422  # a real reason
    assert (await client.post(url, headers=_auth_headers(admin), json={"reason": "Loan abroad, still ours"})).status_code == 200
    assert (await client.get("/admin/real-world-moves", headers=_auth_headers(admin))).json()["mismatches"] == []
    assert (await client.post(url, headers=_auth_headers(admin), json={"reason": "Loan abroad, still ours"})).status_code == 409
    assert (await db.execute(select(AuditEvent).where(AuditEvent.action == "admin.real_world_move.dismissed"))).scalar_one()

    # New evidence: now playing for Bournemouth. That's a different move, so it's reported.
    db.add_all(_played(loaned, "35", "Bournemouth", last=date.today(), fixture="9"))
    await db.commit()
    names = [m["name"] for m in (await client.get("/admin/real-world-moves", headers=_auth_headers(admin))).json()["mismatches"]]
    assert names == ["On Loan Abroad"]
