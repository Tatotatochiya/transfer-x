"""Player history from API-Football, for the player profile ledger
(docs/feature_spec/player-profile-ledger, P1).

Each function fetches one thing and stores it; the backfill script
(`scripts/backfill_player_history.py`) decides which to call, and the
profile page's transfer and injury tabs use the same two refresh functions.
None of these change the player's own record: a past season's club or
position must never overwrite his current one.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.vendor.client import VENDOR, ApiFootballClient


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _date(raw) -> date | None:
    try:
        return date.fromisoformat(str(raw)[:10]) if raw else None
    except ValueError:
        return None


# ── Fetch log: what has been fetched, so a backfill resumes ──────────────────


async def already_fetched(db: AsyncSession, key: str) -> bool:
    from app.stats.models import VendorFetchLog

    return (await db.execute(select(VendorFetchLog.key).where(VendorFetchLog.key == key))).first() is not None


async def mark_fetched(db: AsyncSession, key: str, results: int | None) -> None:
    from app.stats.models import VendorFetchLog

    row = await db.get(VendorFetchLog, key)
    if row is None:
        db.add(VendorFetchLog(key=key, results=results, fetched_at=_now()))
    else:
        row.results, row.fetched_at = results, _now()
    await db.flush()


# ── Season stats ──────────────────────────────────────────────────────────────


async def sync_player_season(db: AsyncSession, player, season: int, client: ApiFootballClient) -> int:
    """Every competition he played in `season` (API-Football's starting year:
    2024 is 2024/25), one PlayerStats row per competition and club. Returns
    the rows stored. Rows are keyed by club as well as competition, so two
    spells in one league in one season stay apart."""
    from app.stats.models import PlayerStats
    from app.vendor.sync import _extract_stat_fields
    from app.vendor.sync import _now as _naive_now  # player_stats.updated_at has no timezone

    resp = await client._get("/players", {"id": int(player.vendor_id), "season": season})
    stored = 0
    for item in resp.get("response") or []:
        for entry in item.get("statistics") or []:
            fields = _extract_stat_fields(entry)
            team = entry.get("team") or {}
            league = entry.get("league") or {}
            league_id = fields["league_id"]
            if not league_id:
                continue
            row = (await db.execute(select(PlayerStats).where(
                PlayerStats.player_id == player.id, PlayerStats.vendor == VENDOR,
                PlayerStats.league_id == league_id, PlayerStats.season == str(season),
                (PlayerStats.team_vendor_id == fields["team_vendor_id"]) | PlayerStats.team_vendor_id.is_(None),
            ))).scalars().first()
            values = {k: v for k, v in fields.items() if k not in ("league_id", "season", "position")}
            values.update(league_name=league.get("name"), league_logo=league.get("logo"), team_logo=team.get("logo"))
            if row is None:
                row = PlayerStats(player_id=player.id, vendor=VENDOR, league_id=league_id, season=str(season),
                                  updated_at=_naive_now(), **values)
                db.add(row)
            else:
                for k, v in values.items():
                    if v is not None:
                        setattr(row, k, v)
                row.updated_at = _naive_now()
            stored += 1
    await db.flush()
    return stored


# ── Transfers and injury periods (also used by the profile's tabs) ───────────


async def refresh_transfers(db: AsyncSession, player, client: ApiFootballClient) -> int:
    """Replace his transfer history from /transfers. Returns the count."""
    from app.players.models import PlayerTransfer

    resp = await client.get_player_transfers(int(player.vendor_id))
    await db.execute(delete(PlayerTransfer).where(PlayerTransfer.player_id == player.id))
    count = 0
    now = _now()
    for item in resp.get("response") or []:
        for t in item.get("transfers") or []:
            teams = t.get("teams") or {}
            team_in, team_out = teams.get("in") or {}, teams.get("out") or {}
            # API-Football puts the fee in "type": "Loan", "€ 42M", "Free", "N/A".
            raw_type = t.get("type") or ""
            is_loan = raw_type.lower() == "loan"
            db.add(PlayerTransfer(
                player_id=player.id, vendor=VENDOR, transfer_date=_date(t.get("date")),
                transfer_type="Loan" if is_loan else "Transfer",
                team_in_vendor_id=str(team_in["id"]) if team_in.get("id") else None,
                team_in_name=team_in.get("name"), team_in_crest_url=team_in.get("logo"),
                team_out_vendor_id=str(team_out["id"]) if team_out.get("id") else None,
                team_out_name=team_out.get("name"), team_out_crest_url=team_out.get("logo"),
                fee_display=None if is_loan or raw_type in ("", "N/A") else raw_type,
                fetched_at=now,
            ))
            count += 1
    await db.flush()
    return count


async def refresh_sidelined(db: AsyncSession, player, client: ApiFootballClient) -> int:
    """Replace his injury periods from /sidelined (type, start, end). Returns
    the count. Games missed are counted later from the matches he missed."""
    from app.players.models import PlayerInjury

    resp = await client.get_player_sidelined(int(player.vendor_id))
    await db.execute(delete(PlayerInjury).where(PlayerInjury.player_id == player.id))
    count = 0
    now = _now()
    for s in resp.get("response") or []:
        db.add(PlayerInjury(
            player_id=player.id, vendor=VENDOR, league_name=None, season=None,
            fixture_date=_date(s.get("start")), end_date=_date(s.get("end")),
            injury_type=s.get("type"), reason=s.get("reason"), games_absent=None, fetched_at=now,
        ))
        count += 1
    await db.flush()
    return count


# ── League-wide: matches missed, club match counts ────────────────────────────


async def sync_league_injuries(db: AsyncSession, league_id: str, season: int, client: ApiFootballClient,
                               players_by_vendor: dict[str, uuid.UUID]) -> int:
    """Every match missed in one competition-season, from /injuries, kept for
    the players we know (`players_by_vendor`: vendor id → player id).
    Returns the rows stored."""
    from app.stats.models import PlayerInjuryFixture

    resp = await client._get("/injuries", {"league": int(league_id), "season": season})
    # What's already stored for this competition-season, loaded once: a
    # season's injuries run to thousands of rows, refreshed twice a day.
    have = {(pid, fid) for pid, fid in (await db.execute(select(
        PlayerInjuryFixture.player_id, PlayerInjuryFixture.fixture_vendor_id).where(
        PlayerInjuryFixture.league_id == str(league_id), PlayerInjuryFixture.season == str(season)))).all()}
    stored = 0
    for item in resp.get("response") or []:
        p = item.get("player") or {}
        pid = players_by_vendor.get(str(p.get("id")))
        fixture = item.get("fixture") or {}
        if pid is None or not fixture.get("id"):
            continue
        fid = str(fixture["id"])
        if (pid, fid) in have or (await db.execute(select(PlayerInjuryFixture.id).where(
                PlayerInjuryFixture.player_id == pid, PlayerInjuryFixture.fixture_vendor_id == fid))).first():
            continue
        have.add((pid, fid))
        league = item.get("league") or {}
        team = item.get("team") or {}
        db.add(PlayerInjuryFixture(
            player_id=pid, fixture_vendor_id=fid, fixture_date=_date(fixture.get("date")),
            league_id=str(league_id), league_name=league.get("name"), season=str(season),
            team_vendor_id=str(team["id"]) if team.get("id") else None,
            injury_type=p.get("type"), reason=p.get("reason"), fetched_at=_now(),
        ))
        stored += 1
    await db.flush()
    return stored


async def sync_team_fixture_count(db: AsyncSession, team_vendor_id: str, league_id: str, season: int,
                                  client: ApiFootballClient) -> int | None:
    """How many matches a club played in one competition-season, from
    /teams/statistics. Returns the count, or None if the API has none."""
    from app.stats.models import TeamSeasonFixtures

    resp = await client._get("/teams/statistics",
                             {"team": int(team_vendor_id), "league": int(league_id), "season": season})
    stats = resp.get("response") or {}
    played = (((stats.get("fixtures") or {}).get("played") or {}).get("total")) if isinstance(stats, dict) else None
    row = (await db.execute(select(TeamSeasonFixtures).where(
        TeamSeasonFixtures.team_vendor_id == str(team_vendor_id), TeamSeasonFixtures.league_id == str(league_id),
        TeamSeasonFixtures.season == str(season)))).scalar_one_or_none()
    if row is None:
        db.add(TeamSeasonFixtures(team_vendor_id=str(team_vendor_id), league_id=str(league_id), season=str(season),
                                  played=played, fetched_at=_now()))
    else:
        row.played, row.fetched_at = played, _now()
    await db.flush()
    return played


# ── Recent matches: ratings for the last-5 chips ─────────────────────────────


async def sync_team_recent_ratings(db: AsyncSession, team_vendor_id: str, client: ApiFootballClient,
                                   players_by_vendor: dict[str, uuid.UUID], last: int = 5) -> tuple[int, int]:
    """A club's last `last` matches, and each of our players' rating in them
    (/fixtures, then /fixtures/players once per match, which covers both
    squads). Returns (matches, ratings stored)."""

    fixtures = (await client._get("/fixtures", {"team": int(team_vendor_id), "last": last})).get("response") or []
    stored = 0
    for f in fixtures:
        stored += await store_fixture_ratings(db, f, client, players_by_vendor)
    return len(fixtures), stored


async def store_fixture_ratings(db: AsyncSession, f: dict, client: ApiFootballClient,
                                players_by_vendor: dict[str, uuid.UUID]) -> int:
    """Each of our players' rating in one match (`f`, an item from /fixtures),
    from /fixtures/players, which covers both squads. Returns ratings stored."""
    from app.stats.models import PlayerFixtureRating

    fixture = f.get("fixture") or {}
    fid = str(fixture.get("id") or "")
    if not fid:
        return 0
    teams = f.get("teams") or {}
    home, away = teams.get("home") or {}, teams.get("away") or {}
    league_name = (f.get("league") or {}).get("name")
    resp = await client._get("/fixtures/players", {"fixture": int(fid)})
    stored = 0
    for side in resp.get("response") or []:
        side_team = side.get("team") or {}
        is_home = side_team.get("id") == home.get("id")
        opponent = away if is_home else home
        for entry in side.get("players") or []:
            pid = players_by_vendor.get(str((entry.get("player") or {}).get("id")))
            if pid is None:
                continue
            games = ((entry.get("statistics") or [{}])[0] or {}).get("games") or {}
            rating = games.get("rating")
            row = (await db.execute(select(PlayerFixtureRating).where(
                PlayerFixtureRating.player_id == pid, PlayerFixtureRating.fixture_vendor_id == fid
            ))).scalar_one_or_none()
            values = dict(
                fixture_date=_date(fixture.get("date")), league_name=league_name,
                team_vendor_id=str(side_team.get("id")) if side_team.get("id") else None,
                opponent_name=opponent.get("name"), opponent_logo=opponent.get("logo"), home=is_home,
                minutes=games.get("minutes"),
                rating=Decimal(str(round(float(rating), 2))) if rating else None, fetched_at=_now(),
            )
            if row is None:
                db.add(PlayerFixtureRating(player_id=pid, fixture_vendor_id=fid, **values))
            else:
                for k, v in values.items():
                    setattr(row, k, v)
            stored += 1
    await db.flush()
    return stored


# ── Loans: mark season rows spent on loan ────────────────────────────────────


async def mark_loan_seasons(db: AsyncSession, player_id: uuid.UUID) -> int:
    """Flag each season row played at a club he had joined on loan: the row's
    club is the club a loan took him to, and the season is the one that loan
    started in (a July-to-June season; a January loan counts for the season
    already under way). Returns rows flagged."""
    from app.players.models import PlayerTransfer
    from app.stats.models import PlayerStats

    loans = (await db.execute(select(PlayerTransfer).where(
        PlayerTransfer.player_id == player_id, PlayerTransfer.transfer_type == "Loan"))).scalars().all()
    loan_spells = set()
    for t in loans:
        if t.transfer_date and t.team_in_vendor_id:
            season = t.transfer_date.year if t.transfer_date.month >= 7 else t.transfer_date.year - 1
            loan_spells.add((t.team_in_vendor_id, str(season)))
    rows = (await db.execute(select(PlayerStats).where(PlayerStats.player_id == player_id))).scalars().all()
    flagged = 0
    for r in rows:
        r.is_loan = (r.team_vendor_id, r.season) in loan_spells
        flagged += bool(r.is_loan)
    await db.flush()
    return flagged
