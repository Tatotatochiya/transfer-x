"""The player profile's season ledger (docs/feature_spec/player-profile-ledger, P2).

Seeded with stored API-Football history; checks the handoff's aggregation
rules, internationals kept apart from club seasons, loans, games missed per
injury, availability and the last five games.
"""

import uuid
from datetime import date
from decimal import Decimal

import pytest
from httpx import AsyncClient

from app.players.ledger import aggregate, season_label, season_of
from tests.conftest import _auth_headers, _register

VENDOR = "api_sports_v3"


def test_aggregation_weights_pass_accuracy_by_minutes_and_rating_by_apps():
    league = {"apps": 20, "starts": 18, "minutes": 1800, "goals": 4, "assists": 2, "shots": 30, "key_passes": 20,
              "passes": 900, "tackles": 30, "interceptions": 10, "duels_won": 100, "duels_total": 180,
              "yellow_cards": 3, "red_cards": 0, "pass_accuracy": 80, "rating": 7.0}
    cup = {**{k: 0 for k in league}, "apps": 2, "minutes": 180, "goals": 1, "pass_accuracy": 90, "rating": 8.0}
    total = aggregate([league, cup])
    assert (total["apps"], total["minutes"], total["goals"]) == (22, 1980, 5)
    assert total["pass_accuracy"] == round((80 * 1800 + 90 * 180) / 1980, 1)
    assert total["rating"] == round((7.0 * 20 + 8.0 * 2) / 22, 2)
    assert season_label("2024") == "2024/25" and season_of(date(2025, 1, 15)) == "2024" and season_of(date(2025, 8, 1)) == "2025"


async def _seed(db) -> uuid.UUID:
    from app.players.models import Player, PlayerInjury, PlayerTransfer
    from app.stats.models import PlayerFixtureRating, PlayerInjuryFixture, PlayerStats, TeamSeasonFixtures

    player = Player(name="Ledger Lad", position="MID", nationality="France", vendor_id="999001")
    db.add(player)
    await db.flush()
    pid = player.id

    def stats(season, team, team_id, league, league_id, apps, minutes, rating, pa, goals=0, loan=False):
        return PlayerStats(player_id=pid, vendor=VENDOR, season=season, team_name=team, team_vendor_id=team_id,
                           league_name=league, league_id=league_id, appearances=apps, lineups=apps, minutes=minutes,
                           goals=goals, assists=0, avg_rating=Decimal(str(rating)), pass_accuracy=pa, is_loan=loan)

    db.add_all([
        stats("2024", "Real Betis", "543", "La Liga", "140", 20, 1800, 7.0, 80, goals=4),
        stats("2024", "Real Betis", "543", "Copa del Rey", "143", 2, 180, 8.0, 90, goals=1),
        stats("2024", "France", "2", "UEFA Nations League", "5", 3, 200, 7.1, 85),
        stats("2023", "Girona", "547", "La Liga", "140", 10, 800, 6.8, 78, loan=True),
        PlayerTransfer(player_id=pid, vendor=VENDOR, transfer_date=date(2023, 8, 1), transfer_type="Loan",
                       team_in_name="Girona", team_out_name="Real Betis"),
        PlayerTransfer(player_id=pid, vendor=VENDOR, transfer_date=date(2024, 7, 1), transfer_type="Transfer",
                       team_in_name="Real Betis", team_out_name="Girona", fee_display="€ 8M"),
        PlayerInjury(player_id=pid, vendor=VENDOR, fixture_date=date(2025, 1, 10), end_date=date(2025, 1, 30),
                     injury_type="Knee Injury"),
        TeamSeasonFixtures(team_vendor_id="543", league_id="140", season="2024", played=38),
        TeamSeasonFixtures(team_vendor_id="543", league_id="143", season="2024", played=4),
    ])
    for i, day in enumerate([date(2025, 1, 12), date(2025, 1, 19), date(2025, 1, 26), date(2025, 3, 1)]):
        db.add(PlayerInjuryFixture(player_id=pid, fixture_vendor_id=f"f{i}", fixture_date=day, league_id="140",
                                   season="2024", team_vendor_id="543", injury_type="Missing Fixture"))
    for i in range(6):
        db.add(PlayerFixtureRating(player_id=pid, fixture_vendor_id=f"r{i}", fixture_date=date(2025, 5, 1 + i),
                                   opponent_name=f"Opponent {i}", rating=Decimal("7.0") + i))
    await db.commit()
    return pid


@pytest.mark.asyncio
async def test_ledger_builds_seasons_injuries_and_recent_games(client: AsyncClient, db):
    pid = await _seed(db)
    viewer = await _register(client, "ledger_viewer@clubs-example.com", club_name="Viewers FC")
    resp = await client.get(f"/players/market/{pid}/ledger", headers=_auth_headers(viewer))
    assert resp.status_code == 200, resp.text
    ledger = resp.json()

    # Club seasons newest first; the national team is kept apart.
    assert [(s["label"], s["club"], s["is_loan"]) for s in ledger["seasons"]] == [
        ("2024/25", "Real Betis", False), ("2023/24", "Girona", True)]
    betis = ledger["seasons"][0]
    assert [c["name"] for c in betis["competitions"]] == ["La Liga", "Copa del Rey"]
    assert (betis["totals"]["apps"], betis["totals"]["goals"], betis["totals"]["rating"]) == (22, 5, round((140 + 16) / 22, 2))
    assert [i["club"] for i in ledger["internationals"]] == ["France"]
    assert ledger["career"]["apps"] == 32  # club football only

    assert [(t["season"], t["type"], t["fee"]) for t in ledger["transfers"]] == [
        ("2024", "Transfer", "€ 8M"), ("2023", "Loan", None)]

    # Three matches fall inside the injury; the fourth (March) doesn't.
    [injury] = ledger["injuries"]["periods"]
    assert (injury["games_missed"], injury["severe"], injury["season"]) == (3, True, "2024")
    season = ledger["injuries"]["by_season"]["2024"]
    assert season["availability"] == round(100 * (1 - 4 / 42))
    assert ledger["injuries"]["by_season"]["2023"]["availability"] is None  # Girona's fixture count unknown

    recent = ledger["form"]["recent"]
    assert len(recent) == 5 and recent[0]["opponent"] == "Opponent 5"


@pytest.mark.asyncio
async def test_signed_out_visitors_get_no_injuries(client: AsyncClient, db):
    pid = await _seed(db)
    resp = await client.get(f"/players/market/{pid}/ledger")
    assert resp.status_code == 200, resp.text
    assert resp.json()["injuries"] is None and resp.json()["seasons"]
    assert (await client.get(f"/players/market/{uuid.uuid4()}/ledger")).status_code == 404
