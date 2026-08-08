"""Sync service: fetch from API-Football, write to DB."""
import asyncio
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.vendor.client import ApiFootballClient, VENDOR
from app.vendor.form import compute_form_score, compute_trend

POSITION_MAP = {
    "goalkeeper": "GK",
    "defender": "DEF",
    "midfielder": "MID",
    "attacker": "FWD",
}


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)  # naive UTC for consistency


def _int(v) -> int | None:
    """Safely cast a value to int, returning None on failure."""
    try:
        return int(v) if v is not None else None
    except (ValueError, TypeError):
        return None


def _extract_stat_fields(stat_entry: dict) -> dict:
    """Extract every useful field from one statistics entry in the API response.

    The stat_entry structure (from api-sports.io /players endpoint):
        {
          "team":       {"id": 42, "name": "Arsenal", "logo": "..."},
          "league":     {"id": 39, "name": "Premier League", "season": 2024, ...},
          "games":      {"appearances": 28, "lineups": 25, "minutes": 2250,
                         "number": 9, "position": "Attacker", "rating": "7.5"},
          "substitutes":{"in": 3, "out": 5, "bench": 2},
          "shots":      {"total": 85, "on": 45},
          "goals":      {"total": 18, "conceded": 0, "assists": 8, "saves": null},
          "passes":     {"total": 450, "key": 35, "accuracy": 75},
          "tackles":    {"total": 12, "blocks": 3, "interceptions": 5},
          "duels":      {"total": 180, "won": 95},
          "dribbles":   {"attempts": 85, "success": 42, "past": 30},
          "fouls":      {"drawn": 45, "committed": 20},
          "cards":      {"yellow": 3, "yellowred": 0, "red": 0},
          "penalty":    {"won": 2, "commited": 1, "scored": 2, "missed": 0, "saved": null}
        }
    """
    from decimal import Decimal

    games       = stat_entry.get("games")       or {}
    goals_data  = stat_entry.get("goals")       or {}
    shots_data  = stat_entry.get("shots")       or {}
    passes      = stat_entry.get("passes")      or {}
    tackles     = stat_entry.get("tackles")     or {}
    duels       = stat_entry.get("duels")       or {}
    dribbles    = stat_entry.get("dribbles")    or {}
    fouls       = stat_entry.get("fouls")       or {}
    cards       = stat_entry.get("cards")       or {}
    penalty     = stat_entry.get("penalty")     or {}
    substitutes = stat_entry.get("substitutes") or {}
    team        = stat_entry.get("team")        or {}
    league      = stat_entry.get("league")      or {}

    rating_raw = games.get("rating")
    avg_rating = Decimal(str(round(float(rating_raw), 2))) if rating_raw else None

    return {
        # Identifiers
        "league_id":      str(league.get("id", "")) or None,
        "season":         str(league.get("season", "")) or None,
        "position":       POSITION_MAP.get((games.get("position") or "").lower()),
        "position_played": POSITION_MAP.get((games.get("position") or "").lower()),
        # Team context
        "team_vendor_id": str(team.get("id")) if team.get("id") else None,
        "team_name":      team.get("name"),
        # Core
        "goals":       _int(goals_data.get("total")) or 0,
        "assists":     _int(goals_data.get("assists")) or 0,
        "appearances": _int(games.get("appearences") or games.get("appearances")) or 0,  # API typo: "appearences"
        "avg_rating":  avg_rating,
        "minutes":     _int(games.get("minutes")),
        # Games detail
        "lineups":      _int(games.get("lineups")),
        "shirt_number": _int(games.get("number")),
        # Substitutions
        "substitutes_in":    _int(substitutes.get("in")),
        "substitutes_out":   _int(substitutes.get("out")),
        "substitutes_bench": _int(substitutes.get("bench")),
        # Shots
        "shots_total":     _int(shots_data.get("total")),
        "shots_on_target": _int(shots_data.get("on")),
        # Passing
        "passes_total":  _int(passes.get("total")),
        "key_passes":    _int(passes.get("key")),
        "pass_accuracy": _int(passes.get("accuracy")),
        # Defending
        "tackles_total": _int(tackles.get("total")),
        "interceptions": _int(tackles.get("interceptions")),
        "blocks":        _int(tackles.get("blocks")),
        # Duels
        "duels_total": _int(duels.get("total")),
        "duels_won":   _int(duels.get("won")),
        # Dribbles
        "dribbles_attempts": _int(dribbles.get("attempts")),
        "dribbles_success":  _int(dribbles.get("success")),
        "dribbles_past":     _int(dribbles.get("past")),
        # Discipline
        "yellow_cards":    _int(cards.get("yellow")),
        "cards_yellowred": _int(cards.get("yellowred")),
        "red_cards":       _int(cards.get("red")),
        "fouls_committed": _int(fouls.get("committed")),
        "fouls_drawn":     _int(fouls.get("drawn")),
        # Goalkeeper
        "saves":          _int(goals_data.get("saves")),
        "goals_conceded": _int(goals_data.get("conceded")),
        # Penalty
        "penalty_scored":    _int(penalty.get("scored")),
        "penalty_missed":    _int(penalty.get("missed")),
        "penalty_won":       _int(penalty.get("won")),
        "penalty_committed": _int(penalty.get("commited")),  # API typo: "commited"
        "penalty_saved":     _int(penalty.get("saved")),
    }


async def sync_player_stats(
    db: AsyncSession,
    player_db_id: uuid.UUID,
    season: int,
    league_id: int,
    client: ApiFootballClient,
) -> dict:
    """Fetch stats for one player (by their DB id) and persist snapshot + PlayerStats.

    Returns a summary dict with keys: player_id, vendor_id, snapshots_created, stats_updated.
    Raises ValueError if player has no vendor_id.
    """
    from app.players.models import Player
    from app.stats.models import PlayerStats, PlayerStatsSnapshot

    player_uuid = uuid.UUID(str(player_db_id))
    result = await db.execute(select(Player).where(Player.id == player_uuid))
    player = result.scalar_one_or_none()
    if player is None:
        raise ValueError("Player not found")
    if not player.vendor_id:
        raise ValueError("Player has no vendor_id — cannot sync from API")

    # Fetch from API
    api_resp = await client.get_player_stats(int(player.vendor_id), season, league_id)
    response_list = api_resp.get("response") or []
    if not response_list:
        return {"player_id": str(player_uuid), "vendor_id": player.vendor_id, "snapshots_created": 0, "stats_updated": False}

    player_data = response_list[0]
    statistics = player_data.get("statistics") or []

    # Update player photo if available
    api_player = player_data.get("player") or {}
    if api_player.get("photo") and not player.photo_url:
        player.photo_url = api_player["photo"]

    snapshots_created = 0
    stats_updated = False

    for stat_entry in statistics:
        fields = _extract_stat_fields(stat_entry)
        api_league_id = fields["league_id"] or str(league_id)
        api_season = fields["season"] or str(season)

        # Create snapshot with full stat payload
        snapshot = PlayerStatsSnapshot(
            player_id=player_uuid,
            vendor=VENDOR,
            payload=stat_entry,
            fetched_at=_now(),
        )
        db.add(snapshot)
        snapshots_created += 1

        # Upsert PlayerStats
        stats_result = await db.execute(
            select(PlayerStats).where(
                PlayerStats.player_id == player_uuid,
                PlayerStats.vendor == VENDOR,
                PlayerStats.league_id == api_league_id,
                PlayerStats.season == api_season,
            )
        )
        stats_row = stats_result.scalar_one_or_none()

        stat_kwargs = {k: v for k, v in fields.items() if k not in ("league_id", "season", "position")}

        if stats_row:
            for k, v in stat_kwargs.items():
                if v is not None:
                    setattr(stats_row, k, v)
            stats_row.updated_at = _now()
        else:
            stats_row = PlayerStats(
                player_id=player_uuid,
                vendor=VENDOR,
                league_id=api_league_id,
                season=api_season,
                updated_at=_now(),
                **stat_kwargs,
            )
            db.add(stats_row)
        stats_updated = True

        if fields["position"] and not player.position:
            player.position = fields["position"]

        # Same rule as the league/team sync path: never overwrite team_name for
        # a player currently under a TransferX contract.
        if fields.get("team_name") and player.current_club_id is None:
            player.team_name = fields["team_name"]

    await db.flush()
    return {
        "player_id": str(player_uuid),
        "vendor_id": player.vendor_id,
        "snapshots_created": snapshots_created,
        "stats_updated": stats_updated,
    }


async def _upsert_player_from_api_data(
    db: AsyncSession,
    player_data: dict,
    season: int,
    created_by_user_id: uuid.UUID | None = None,
) -> tuple[bool, int]:
    """Upsert a single player + their stats snapshots from one API response item.

    Returns (player_created: bool, snapshots_created: int).
    """
    from app.players.models import Player, PlayerStatus, PlayerVisibility
    from app.stats.models import PlayerStats, PlayerStatsSnapshot

    api_player = player_data.get("player") or {}
    statistics = player_data.get("statistics") or []

    vendor_id = str(api_player.get("id", ""))
    if not vendor_id:
        return False, 0

    p_result = await db.execute(select(Player).where(Player.vendor_id == vendor_id))
    player = p_result.scalar_one_or_none()
    player_created = False

    # Parse birth date once
    birth = api_player.get("birth") or {}
    birth_date_raw = birth.get("date")
    birth_date: date | None = None
    if birth_date_raw:
        try:
            birth_date = date.fromisoformat(birth_date_raw)
        except ValueError:
            pass

    if not player:
        position = None
        for stat_entry in statistics:
            games = stat_entry.get("games") or {}
            position = POSITION_MAP.get((games.get("position") or "").lower())
            if position:
                break

        player = Player(
            name=api_player.get("name", "Unknown"),
            firstname=api_player.get("firstname"),
            lastname=api_player.get("lastname"),
            age=api_player.get("age"),
            nationality=api_player.get("nationality"),
            height=api_player.get("height"),
            weight=api_player.get("weight"),
            birth_date=birth_date,
            birth_place=birth.get("place"),
            birth_country=birth.get("country"),
            position=position,
            photo_url=api_player.get("photo"),
            vendor_id=vendor_id,
            status=PlayerStatus.FREE_AGENT,
            visibility=PlayerVisibility.PUBLIC,
            created_by_user_id=created_by_user_id,
        )
        db.add(player)
        await db.flush()
        player_created = True
    else:
        if api_player.get("photo") and not player.photo_url:
            player.photo_url = api_player["photo"]
        # Backfill bio fields from API if not yet set
        if api_player.get("firstname") and not player.firstname:
            player.firstname = api_player["firstname"]
        if api_player.get("lastname") and not player.lastname:
            player.lastname = api_player["lastname"]
        if api_player.get("height") and not player.height:
            player.height = api_player["height"]
        if api_player.get("weight") and not player.weight:
            player.weight = api_player["weight"]
        if birth_date and not player.birth_date:
            player.birth_date = birth_date
        if birth.get("place") and not player.birth_place:
            player.birth_place = birth["place"]
        if birth.get("country") and not player.birth_country:
            player.birth_country = birth["country"]

    # Set denormalized team_name from first stat entry that has one — but never
    # for a player currently under a TransferX contract. current_club_id (set
    # only via an active Contract, see players/service.normalize_player_status)
    # is authoritative then; overwriting team_name would leave stale vendor
    # data to silently resurface once the contract lapses.
    if player.current_club_id is None:
        for stat_entry in statistics:
            team = stat_entry.get("team") or {}
            if team.get("name"):
                player.team_name = team["name"]
                break

    player_uuid = uuid.UUID(str(player.id))
    snapshots_created = 0

    for stat_entry in statistics:
        fields = _extract_stat_fields(stat_entry)
        api_league_id = fields["league_id"] or ""
        api_season_str = fields["season"] or str(season)

        snapshot = PlayerStatsSnapshot(
            player_id=player_uuid,
            vendor=VENDOR,
            payload=stat_entry,
            fetched_at=_now(),
        )
        db.add(snapshot)
        snapshots_created += 1

        stats_result = await db.execute(
            select(PlayerStats).where(
                PlayerStats.player_id == player_uuid,
                PlayerStats.vendor == VENDOR,
                PlayerStats.league_id == api_league_id,
                PlayerStats.season == api_season_str,
            )
        )
        stats_row = stats_result.scalar_one_or_none()

        stat_kwargs = {k: v for k, v in fields.items() if k not in ("league_id", "season", "position")}

        if stats_row:
            for k, v in stat_kwargs.items():
                if v is not None:
                    setattr(stats_row, k, v)
            stats_row.updated_at = _now()
        else:
            stats_row = PlayerStats(
                player_id=player_uuid,
                vendor=VENDOR,
                league_id=api_league_id,
                season=api_season_str,
                updated_at=_now(),
                **stat_kwargs,
            )
            db.add(stats_row)

    return player_created, snapshots_created


async def sync_league(
    db: AsyncSession,
    league_id: int,
    season: int,
    client: ApiFootballClient,
    sleep_ms: int = 0,
    created_by_user_id: uuid.UUID | None = None,
) -> dict:
    """Sync all players for a league. Returns summary counts."""
    from app.world.models import WorldLeague

    players_created = 0
    players_updated = 0
    snapshots_created = 0

    # Upsert WorldLeague
    wl_result = await db.execute(
        select(WorldLeague).where(
            WorldLeague.vendor == VENDOR,
            WorldLeague.league_id == str(league_id),
        )
    )
    wl = wl_result.scalar_one_or_none()
    if not wl:
        wl = WorldLeague(
            vendor=VENDOR,
            league_id=str(league_id),
            name=f"League {league_id}",
            season=str(season),
        )
        db.add(wl)
    else:
        wl.season = str(season)

    # Paginate through league players
    page = 1
    total_pages = 1
    while page <= total_pages:
        resp = await client.get_league_players(league_id, season, page)
        paging = resp.get("paging") or {}
        total_pages = int(paging.get("total") or 1)
        response_list = resp.get("response") or []

        for player_data in response_list:
            created, snaps = await _upsert_player_from_api_data(
                db, player_data, season, created_by_user_id
            )
            if created:
                players_created += 1
            else:
                players_updated += 1
            snapshots_created += snaps

            # Update WorldLeague name from the first stat entry that has it
            for stat_entry in (player_data.get("statistics") or []):
                league_info = stat_entry.get("league") or {}
                league_name = league_info.get("name")
                league_country = league_info.get("country")
                if league_name and wl.name == f"League {league_id}":
                    wl.name = league_name
                if league_country and not wl.country:
                    wl.country = league_country

        await db.flush()
        if sleep_ms > 0:
            await asyncio.sleep(sleep_ms / 1000)
        page += 1

    return {
        "league_id": league_id,
        "season": season,
        "pages_synced": page - 1,
        "players_created": players_created,
        "players_updated": players_updated,
        "snapshots_created": snapshots_created,
    }


async def sync_team(
    db: AsyncSession,
    team_id: int,
    season: int,
    client: ApiFootballClient,
    sleep_ms: int = 0,
    created_by_user_id: uuid.UUID | None = None,
) -> dict:
    """Sync all players for a specific team. Returns summary counts."""
    players_created = 0
    players_updated = 0
    snapshots_created = 0

    page = 1
    total_pages = 1
    while page <= total_pages:
        resp = await client.get_team_players(team_id, season, page)
        paging = resp.get("paging") or {}
        total_pages = int(paging.get("total") or 1)
        response_list = resp.get("response") or []

        for player_data in response_list:
            created, snaps = await _upsert_player_from_api_data(
                db, player_data, season, created_by_user_id
            )
            if created:
                players_created += 1
            else:
                players_updated += 1
            snapshots_created += snaps

        await db.flush()
        if sleep_ms > 0:
            await asyncio.sleep(sleep_ms / 1000)
        page += 1

    return {
        "team_id": team_id,
        "season": season,
        "pages_synced": page - 1,
        "players_created": players_created,
        "players_updated": players_updated,
        "snapshots_created": snapshots_created,
    }


async def compute_all_form(
    db: AsyncSession,
    *,
    vendor: str = VENDOR,
    season: str | None = None,
    window_games: int = 5,
) -> int:
    """Compute PlayerForm for all players with snapshots. Returns count updated."""
    from app.stats.models import PlayerForm, PlayerStatsSnapshot

    # Get distinct player_ids that have snapshots
    from sqlalchemy import distinct
    pid_result = await db.execute(
        select(distinct(PlayerStatsSnapshot.player_id)).where(
            PlayerStatsSnapshot.vendor == vendor
        )
    )
    player_ids = [uuid.UUID(str(r)) for r in pid_result.scalars()]

    count = 0
    for player_id in player_ids:
        # Load all snapshots for this player, ordered newest first
        snap_q = (
            select(PlayerStatsSnapshot)
            .where(
                PlayerStatsSnapshot.player_id == player_id,
                PlayerStatsSnapshot.vendor == vendor,
            )
            .order_by(PlayerStatsSnapshot.fetched_at.desc())
        )
        snap_result = await db.execute(snap_q)
        snapshots = list(snap_result.scalars())
        if not snapshots:
            continue

        payloads = [s.payload for s in snapshots]
        form_data = compute_form_score(payloads, window_games)
        if form_data is None:
            continue
        trend = compute_trend(payloads, window_games)

        # Upsert PlayerForm
        form_result = await db.execute(
            select(PlayerForm).where(PlayerForm.player_id == player_id)
        )
        form_row = form_result.scalar_one_or_none()
        if form_row:
            form_row.form_score = form_data["form_score"]
            form_row.games_considered = form_data["games_considered"]
            form_row.key_metrics = form_data["key_metrics"]
            form_row.trend = trend
            form_row.last_updated = _now()
        else:
            form_row = PlayerForm(
                player_id=player_id,
                form_score=form_data["form_score"],
                games_considered=form_data["games_considered"],
                key_metrics=form_data["key_metrics"],
                trend=trend,
                last_updated=_now(),
            )
            db.add(form_row)
        count += 1

    await db.flush()
    return count
