"""The player profile's season ledger (docs/feature_spec/player-profile-ledger, P2).

One read model for the Overview, Career and Injuries tabs: club seasons
(one row per season and club, with a sub-row per competition), internationals
kept apart, a career total, transfers placed in their seasons, injury
periods with games missed, availability, and his last five games. Every
figure is computed here from stored API-Football data (app/vendor/history.py);
nothing comes from a model.

Aggregation rules (HANDOFF.md "Data requirements"): counts are summed; pass
accuracy is weighted by minutes; rating by appearances.
"""
from __future__ import annotations

import re
import uuid
from collections import defaultdict
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

COUNTS = ("apps", "starts", "minutes", "goals", "assists", "shots", "key_passes", "passes",
          "tackles", "interceptions", "duels_won", "duels_total", "yellow_cards", "red_cards")
SEVERE = re.compile(r"knee|ankle|ligament|acl|cruciate|achilles|fracture|broken|surgery", re.I)
_YOUTH = re.compile(r"\s+U\d{2}$", re.I)


def season_label(season: str | int) -> str:
    s = int(season)
    return f"{s}/{(s + 1) % 100:02d}"


def season_of(day: date) -> str:
    """The season a date falls in: July to June, named by its first year."""
    return str(day.year if day.month >= 7 else day.year - 1)


def _row_stats(r) -> dict:
    return {
        "apps": r.appearances or 0, "starts": r.lineups or 0, "minutes": r.minutes or 0,
        "goals": r.goals or 0, "assists": r.assists or 0, "shots": r.shots_total or 0,
        "key_passes": r.key_passes or 0, "passes": r.passes_total or 0,
        "tackles": r.tackles_total or 0, "interceptions": r.interceptions or 0,
        "duels_won": r.duels_won or 0, "duels_total": r.duels_total or 0,
        "yellow_cards": r.yellow_cards or 0, "red_cards": r.red_cards or 0,
        "pass_accuracy": r.pass_accuracy, "rating": float(r.avg_rating) if r.avg_rating is not None else None,
    }


def aggregate(parts: list[dict]) -> dict:
    """Sum the counts; pass accuracy weighted by minutes, rating by
    appearances, over the parts that have them."""
    out = {k: sum(p[k] for p in parts) for k in COUNTS}
    pa = [(p["pass_accuracy"], p["minutes"]) for p in parts if p["pass_accuracy"] is not None and p["minutes"]]
    out["pass_accuracy"] = round(sum(a * m for a, m in pa) / sum(m for _, m in pa), 1) if pa else None
    rt = [(p["rating"], p["apps"]) for p in parts if p["rating"] is not None and p["apps"]]
    out["rating"] = round(sum(r * n for r, n in rt) / sum(n for _, n in rt), 2) if rt else None
    return out


async def _countries(db: AsyncSession) -> set[str]:
    """Names national teams go by: every nationality and team country we hold."""
    from app.players.models import Player
    from app.world.models import WorldTeam

    names = set((await db.execute(select(Player.nationality).distinct())).scalars())
    names |= set((await db.execute(select(WorldTeam.country).distinct())).scalars())
    return {n.lower() for n in names if n}


async def build_ledger(db: AsyncSession, player, *, include_injuries: bool) -> dict:
    from app.players.models import PlayerInjury, PlayerTransfer
    from app.stats.models import (PlayerFixtureRating, PlayerForm, PlayerInjuryFixture, PlayerStats,
                                  TeamSeasonFixtures)

    rows = (await db.execute(select(PlayerStats).where(PlayerStats.player_id == player.id))).scalars().all()
    countries = await _countries(db)

    # ── Seasons: one row per season and club; internationals apart ─────────
    clubs: dict[tuple[str, str], list] = defaultdict(list)
    internationals: dict[tuple[str, str], list] = defaultdict(list)
    for r in rows:
        if not r.season or not (r.appearances or 0):
            continue
        team = r.team_name or "Unknown"
        national = _YOUTH.sub("", team).lower() in countries
        # Club friendlies (pre-season) aren't competitive football; an
        # international friendly is still a cap, so those stay.
        if not national and (r.league_name or "").lower().startswith("friendlies"):
            continue
        (internationals if national else clubs)[(r.season, team)].append(r)

    def build_rows(groups: dict) -> list[dict]:
        out = []
        for (season, team), parts in groups.items():
            comps = sorted(parts, key=lambda r: -(r.appearances or 0))
            stats = [_row_stats(r) for r in comps]
            out.append({
                "season": season, "label": season_label(season), "club": team,
                "club_logo": next((r.team_logo for r in comps if r.team_logo), None),
                "is_loan": any(r.is_loan for r in comps),
                "totals": aggregate(stats),
                "competitions": [{"name": r.league_name or "Other", "logo": r.league_logo, **s}
                                 for r, s in zip(comps, stats)],
            })
        # Newest season first; within a season, the club he played most for first.
        return sorted(out, key=lambda x: (-int(x["season"]), -x["totals"]["apps"]))

    seasons = build_rows(clubs)
    career = aggregate([s["totals"] for s in seasons]) if seasons else None

    # ── Transfers, placed in the season they happened in ───────────────────
    transfers = (await db.execute(select(PlayerTransfer).where(PlayerTransfer.player_id == player.id)
                                  .order_by(PlayerTransfer.transfer_date.desc().nulls_last()))).scalars().all()
    moves = [{
        "date": t.transfer_date.isoformat() if t.transfer_date else None,
        "season": season_of(t.transfer_date) if t.transfer_date else None,
        "type": t.transfer_type, "fee": t.fee_display,
        "from": t.team_out_name, "from_logo": t.team_out_crest_url,
        "to": t.team_in_name, "to_logo": t.team_in_crest_url,
    } for t in transfers]

    # ── Injuries: periods, games missed, availability ──────────────────────
    injuries = None
    if include_injuries:
        periods = (await db.execute(select(PlayerInjury).where(PlayerInjury.player_id == player.id)
                                    .order_by(PlayerInjury.fixture_date.desc().nulls_last()))).scalars().all()
        missed = (await db.execute(select(PlayerInjuryFixture).where(
            PlayerInjuryFixture.player_id == player.id,
            PlayerInjuryFixture.injury_type == "Missing Fixture"))).scalars().all()
        today = date.today()
        items = []
        for p in periods:
            if p.fixture_date is None:
                continue
            end = p.end_date or today
            games = sum(1 for m in missed if m.fixture_date and p.fixture_date <= m.fixture_date <= end)
            items.append({
                "start": p.fixture_date.isoformat(), "end": p.end_date.isoformat() if p.end_date else None,
                "type": p.injury_type, "season": season_of(p.fixture_date),
                "games_missed": games, "severe": bool(SEVERE.search(p.injury_type or "")),
            })
        # Availability: matches missed against the matches his clubs played in
        # the competitions he played that season.
        counts = (await db.execute(select(TeamSeasonFixtures))).scalars().all()
        played = {(c.team_vendor_id, c.league_id, c.season): c.played for c in counts}
        by_season = {}
        for s in {r.season for r in rows if r.season}:
            spells = [(r.team_vendor_id, r.league_id) for r in rows
                      if r.season == s and (r.appearances or 0) and _YOUTH.sub("", r.team_name or "").lower() not in countries
                      and not (r.league_name or "").lower().startswith("friendlies")]
            total = sum(played.get((t, lg, s)) or 0 for t, lg in spells)
            known = all(played.get((t, lg, s)) is not None for t, lg in spells) and total > 0
            lost = sum(1 for m in missed if m.season == s and (m.team_vendor_id, m.league_id) in set(spells))
            season_items = [i for i in items if i["season"] == s]
            by_season[s] = {
                "injuries": len(season_items),
                "games_missed": sum(i["games_missed"] for i in season_items),
                "longest": max((i["games_missed"] for i in season_items), default=0),
                "availability": round(100 * (1 - lost / total)) if known else None,
            }
        injuries = {"periods": items, "by_season": by_season}

    # ── Form and his last five games ───────────────────────────────────────
    form = (await db.execute(select(PlayerForm).where(PlayerForm.player_id == player.id))).scalars().first()
    recent = (await db.execute(select(PlayerFixtureRating).where(PlayerFixtureRating.player_id == player.id)
                               .order_by(PlayerFixtureRating.fixture_date.desc()).limit(5))).scalars().all()

    return {
        "player_id": str(player.id),
        "seasons": seasons,
        "career": career,
        "internationals": build_rows(internationals),
        "transfers": moves,
        "injuries": injuries,
        "form": {
            "score": float(form.form_score) if form else None,
            "trend": float(form.trend) if form and form.trend is not None else None,
            "recent": [{"date": g.fixture_date.isoformat() if g.fixture_date else None, "opponent": g.opponent_name,
                        "opponent_logo": g.opponent_logo, "home": g.home, "minutes": g.minutes,
                        "rating": float(g.rating) if g.rating is not None else None, "competition": g.league_name}
                       for g in recent],
        },
    }
