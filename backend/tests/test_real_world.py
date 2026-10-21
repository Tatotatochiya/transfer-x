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


# ── The nightly transfers step, and telling the club ─────────────────────────


@pytest.mark.asyncio
async def test_the_nightly_transfers_step_finds_a_move_before_any_game(db, clubs):
    from app.jobs import daily_refresh as dr

    moved = await _contracted(db, clubs["Bournemouth"], "Not Played Yet", started=date(2020, 7, 1))
    broken = await _contracted(db, clubs["Bournemouth"], "Broken Feed", started=date(2020, 7, 1))
    from app.players.models import Player
    for p, vid in ((moved, "111"), (broken, "222")):
        (await db.get(Player, p.id)).vendor_id = vid
    await db.commit()
    moved_id = moved.id
    assert await _check(db, moved) is None  # nothing on record yet

    class Fake:
        async def get_player_transfers(self, vendor_id):
            if vendor_id == 222:
                raise RuntimeError("API-Football hiccup")
            return {"response": [{"transfers": [{"date": "2026-08-30", "type": "€ 12M",
                                                 "teams": {"in": {"id": 47, "name": "Tottenham"},
                                                           "out": {"id": 35, "name": "Bournemouth"}}}]}]}

    summary, failures = {}, []
    await dr.step_transfers(db, Fake(), [], summary, failures)
    assert summary["transfers_refreshed"] == 1 and failures == ["transfers: 1 players failed"]  # one failing stops nothing
    player = await db.get(Player, moved_id)
    move = await _check(db, player)
    assert (move["real_club"], move["fee"], move["moved_on"]) == ("Tottenham", "€ 12M", "2026-08-30")


@pytest.mark.asyncio
async def test_clubs_hear_once_per_set_of_moved_players(db, clubs):
    from app.notifications.models import Notification, NotificationType
    from app.players import real_world

    senesi = await _contracted(db, clubs["Bournemouth"], "M. Senesi", started=date(2020, 7, 1))
    db.add(_transfer(senesi, date.today(), "47", "Tottenham", fee="Free agent"))
    await db.commit()

    async def alerts():
        return (await db.execute(select(Notification).where(
            Notification.type == NotificationType.REAL_WORLD_MOVES))).scalars().all()

    assert await real_world.alert_clubs(db) == 1
    await db.commit()
    first = await alerts()
    assert len(first) >= 1 and "M. Senesi (Tottenham)" in first[0].message
    assert "TransferX staff will update your squad" in first[0].message

    await real_world.alert_clubs(db)  # the hourly job again: nothing new, nobody told twice
    await db.commit()
    assert len(await alerts()) == len(first)

    other = await _contracted(db, clubs["Bournemouth"], "Also Gone", started=date(2020, 7, 1))
    db.add(_transfer(other, date.today(), "2932", "Al-Hilal Saudi FC"))
    await db.commit()
    await real_world.alert_clubs(db)  # the list grew: a new notification naming both
    await db.commit()
    latest = await alerts()
    assert len(latest) == 2 * len(first)
    assert "2 of your players" in latest[-1].message and "Also Gone" in latest[-1].message


# ── TransferX's own deals (2026-10-21) ───────────────────────────────────────


async def _bought(db, buyer: dict, seller: dict, name: str, on=date(2026, 9, 30), fee=45_000_000):
    """A player TransferX moved from `seller` to `buyer`: a completed deal and his new contract."""
    from datetime import datetime, timezone
    from decimal import Decimal

    from app.deals.models import Deal, DealStage, DealStatus

    p = await _contracted(db, buyer, name, started=on)
    db.add(Deal(buyer_club_id=buyer["id"], seller_club_id=seller["id"], player_id=p.id, agreed_fee=Decimal(fee),
                status=DealStatus.COMPLETED, stage=DealStage.COMPLETED,
                completed_at=datetime(on.year, on.month, on.day, 12, tzinfo=timezone.utc)))
    await db.commit()
    return p


def _game(player, team, day, fixture):
    from app.stats.models import PlayerFixtureRating

    return PlayerFixtureRating(player_id=player.id, fixture_vendor_id=fixture, fixture_date=day,
                               team_vendor_id=team, minutes=90)


async def _open_deal(client, db, clubs, player, buyer_tokens, *, confirmed=True) -> str:
    """An accepted offer for `player` (at Bournemouth) from `buyer_tokens`, moved on to
    CONFIRMED, awaiting completion, when `confirmed`."""
    from app.deals.models import Deal, DealStage, DealStatus
    from tests.test_deals import _give_budget

    await _give_budget(db)
    offer = (await client.post("/offers", headers=_auth_headers(buyer_tokens), json={
        "player_id": str(player.id), "to_club_id": str(clubs["Bournemouth"]["id"]), "fee_amount": 2_000_000})).json()
    accepted = await client.post(f"/offers/{offer['id']}/accept", headers=_auth_headers(clubs["Bournemouth"]["tokens"]))
    assert accepted.status_code == 200, accepted.text
    deal = (await db.execute(select(Deal).where(Deal.player_id == player.id))).scalar_one()
    deal_id = deal.id
    if confirmed:
        deal.stage, deal.status = DealStage.CONFIRMED, DealStatus.PENDING_COMPLETION
        await db.commit()
    return str(deal_id)


@pytest.mark.asyncio
async def test_games_before_his_transferx_move_are_the_data_catching_up(db, clubs):
    rice = await _bought(db, clubs["Tottenham"], clubs["Bournemouth"], "D. Rice")
    db.add_all(_played(rice, "35", "Bournemouth", last=date(2026, 9, 20)))
    db.add(_transfer(rice, date(2026, 7, 1), "35", "Bournemouth"))
    await db.commit()
    assert await _check(db, rice) is None


@pytest.mark.asyncio
async def test_playing_on_for_the_old_club_is_for_staff_and_cant_be_applied(client: AsyncClient, db, clubs):
    from app.notifications.models import Notification, NotificationType
    from app.players import real_world

    admin = await _admin(client, db)
    rice = await _bought(db, clubs["Tottenham"], clubs["Bournemouth"], "D. Rice")
    db.add_all(_played(rice, "35", "Bournemouth", last=date(2026, 9, 20)))
    db.add(_game(rice, "35", date(2026, 10, 5), "2"))  # after his TransferX move
    await db.commit()

    move = await _check(db, rice)
    assert move["case"] == "behind_transferx"
    assert move["transferx_move"]["from_club"] == "Bournemouth" and move["transferx_move"]["on"] == "2026-09-30"
    listing = (await client.get("/admin/real-world-moves", headers=_auth_headers(admin))).json()
    [row] = [m for m in listing["mismatches"] if m["name"] == "D. Rice"]
    assert "Moving him back would undo a paid transfer" in row["apply_blocked"]
    assert "for £45m" in row["apply_blocked"]
    assert listing["counts"]["behind_transferx"] == 1
    assert (await _apply(client, admin, rice))["applied"] == []

    # Only staff see it; the clubs aren't alerted.
    as_club = (await client.get(f"/players/market/{rice.id}/ledger", headers=_auth_headers(clubs["Tottenham"]["tokens"]))).json()
    assert as_club["real_world"] is None
    as_staff = (await client.get(f"/players/market/{rice.id}/ledger", headers=_auth_headers(admin))).json()
    assert as_staff["real_world"]["case"] == "behind_transferx"
    await real_world.alert_clubs(db)
    await db.commit()
    assert (await db.execute(select(Notification).where(Notification.type == NotificationType.REAL_WORLD_MOVES))).first() is None

    # Confirming his registration is how staff close it.
    resp = await client.post(f"/admin/real-world-moves/{rice.id}/dismiss", headers=_auth_headers(admin),
                             json={"reason": "TransferX registration confirmed"})
    assert resp.status_code == 200, resp.text
    assert await _check(db, rice) is None


@pytest.mark.asyncio
async def test_an_open_deal_waits_for_staff_before_it_can_complete(client: AsyncClient, db, clubs):
    from app.deals.models import Deal, DealStatus
    from app.notifications.models import Notification, NotificationType
    from app.players import real_world

    rival = await _register(client, "rival3@rw-example.com", club_name="Rival Three")
    admin = await _admin(client, db)
    saka = await _contracted(db, clubs["Bournemouth"], "B. Saka", started=date(2020, 7, 1))
    db.add(_transfer(saka, date.today(), "2932", "Al-Hilal Saudi FC"))
    await db.commit()
    deal_id = await _open_deal(client, db, clubs, saka, rival)

    notice = (await client.get(f"/deals/{deal_id}/real-world", headers=_auth_headers(rival))).json()
    assert "TransferX staff are checking his registration" in notice["hold"]
    held = await client.post(f"/deals/{deal_id}/advance", headers=_auth_headers(rival))
    assert held.status_code in (400, 409) and "playing for Al-Hilal Saudi FC" in held.text
    listing = (await client.get("/admin/real-world-moves", headers=_auth_headers(admin))).json()
    [row] = [m for m in listing["mismatches"] if m["name"] == "B. Saka"]
    assert row["open_deal"]["id"] == deal_id and row["open_deal"]["buyer_club"] == "Rival Three"
    assert listing["counts"]["in_deal"] == 1

    # Both clubs are told, on the deal, once.
    for _ in range(2):
        await real_world.alert_clubs(db)
        await db.commit()
    on_deal = (await db.execute(select(Notification).where(
        Notification.type == NotificationType.REAL_WORLD_MOVES, Notification.link == f"/deals/{deal_id}"))).scalars().all()
    rival_id = uuid.UUID(await _get_club_id(client, _auth_headers(rival)))
    from app.notifications.service import club_member_user_ids
    told = {n.recipient_user_id for n in on_deal}
    assert told == set(await club_member_user_ids(db, rival_id)) | set(await club_member_user_ids(db, clubs["Bournemouth"]["id"]))

    # Staff confirm his registration: the deal completes.
    await client.post(f"/admin/real-world-moves/{saka.id}/dismiss", headers=_auth_headers(admin),
                      json={"reason": "Checked with both clubs: registration is right"})
    assert (await client.get(f"/deals/{deal_id}/real-world", headers=_auth_headers(rival))).json()["hold"] is None
    done = await client.post(f"/deals/{deal_id}/advance", headers=_auth_headers(rival))
    assert done.status_code == 200, done.text
    db.expire_all()
    assert (await db.get(Deal, uuid.UUID(deal_id))).status == DealStatus.COMPLETED


@pytest.mark.asyncio
async def test_staff_complete_overrides_the_hold(client: AsyncClient, db, clubs):
    rival = await _register(client, "rival4@rw-example.com", club_name="Rival Four")
    admin = await _admin(client, db)
    p = await _contracted(db, clubs["Bournemouth"], "Held Harry", started=date(2020, 7, 1))
    db.add(_transfer(p, date.today(), "2932", "Al-Hilal Saudi FC"))
    await db.commit()
    deal_id = await _open_deal(client, db, clubs, p, rival)
    resp = await client.post(f"/admin/deals/{deal_id}/complete", headers=_auth_headers(admin),
                             json={"reason": "Registration confirmed with the league"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "COMPLETED"


@pytest.mark.asyncio
async def test_at_the_buying_club_in_real_life_is_no_conflict(client: AsyncClient, db, clubs):
    p = await _contracted(db, clubs["Bournemouth"], "Catching Up", started=date(2020, 7, 1))
    db.add(_transfer(p, date.today(), "47", "Tottenham"))
    await db.commit()
    deal_id = await _open_deal(client, db, clubs, p, clubs["Tottenham"]["tokens"])
    assert await _check(db, p) is None
    notice = (await client.get(f"/deals/{deal_id}/real-world", headers=_auth_headers(clubs["Tottenham"]["tokens"]))).json()
    assert notice == {"hold": None, "note": None}
    done = await client.post(f"/deals/{deal_id}/advance", headers=_auth_headers(clubs["Tottenham"]["tokens"]))
    assert done.status_code == 200, done.text


@pytest.mark.asyncio
async def test_a_loan_elsewhere_is_a_note_not_a_hold(client: AsyncClient, db, clubs):
    rival = await _register(client, "rival5@rw-example.com", club_name="Rival Five")
    p = await _contracted(db, clubs["Bournemouth"], "Loaned Larry", started=date(2020, 7, 1))
    db.add(_transfer(p, date.today(), "2932", "Al-Hilal Saudi FC", kind="Loan"))
    await db.commit()
    deal_id = await _open_deal(client, db, clubs, p, rival)
    notice = (await client.get(f"/deals/{deal_id}/real-world", headers=_auth_headers(rival))).json()
    assert notice["hold"] is None and "on loan at Al-Hilal Saudi FC" in notice["note"]
    assert (await client.post(f"/deals/{deal_id}/advance", headers=_auth_headers(rival))).status_code == 200


@pytest.mark.asyncio
async def test_collapse_and_apply_ends_the_deal_then_moves_him(client: AsyncClient, db, clubs):
    from app.deals.models import Deal, DealStatus
    from app.players.models import Player, PlayerStatus
    from tests.test_deals import _get_finance

    rival = await _register(client, "rival6@rw-example.com", club_name="Rival Six")
    admin = await _admin(client, db)
    p = await _contracted(db, clubs["Bournemouth"], "Gone Gary", started=date(2020, 7, 1))
    db.add(_transfer(p, date.today(), "2932", "Al-Hilal Saudi FC"))
    await db.commit()
    pid = p.id
    deal_id = await _open_deal(client, db, clubs, p, rival, confirmed=False)
    assert float((await _get_finance(client, _auth_headers(rival)))["transfer_committed"]) == 2_000_000

    # Applying on its own is refused while the deal is open.
    assert "in a deal on TransferX" in (await _apply(client, admin, p))["skipped"][0]["reason"]
    resp = await client.post(f"/admin/real-world-moves/{pid}/collapse-and-apply", headers=_auth_headers(admin),
                             json={"reason": "He joined Al-Hilal in the summer"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["collapsed_deal_id"] == deal_id
    db.expire_all()
    assert (await db.get(Deal, uuid.UUID(deal_id))).status == DealStatus.COLLAPSED
    assert (await db.get(Player, pid)).status == PlayerStatus.EXTERNAL
    assert float((await _get_finance(client, _auth_headers(rival)))["transfer_committed"]) == 0
    # Nothing left to do it to.
    again = await client.post(f"/admin/real-world-moves/{pid}/collapse-and-apply", headers=_auth_headers(admin),
                              json={"reason": "He joined Al-Hilal in the summer"})
    assert again.status_code == 409
