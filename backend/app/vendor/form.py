"""Form score computation (mirrors Django's compute_player_form algorithm)."""
from decimal import Decimal


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _extract_metrics(payload: dict) -> dict:
    """Extract goals/assists/minutes/avg_rating from a snapshot payload.

    The payload is one statistics entry from the API response:
    {"games": {"minutes": 90, "rating": "8.2", ...}, "goals": {"total": 1, "assists": 0, ...}}
    """
    games = payload.get("games") or {}
    goals_data = payload.get("goals") or {}
    rating_raw = games.get("rating")
    return {
        "minutes": int(games["minutes"]) if games.get("minutes") else 0,
        "goals": int(goals_data["total"]) if goals_data.get("total") else 0,
        "assists": int(goals_data["assists"]) if goals_data.get("assists") else 0,
        "avg_rating": float(rating_raw) if rating_raw else None,
    }


def compute_form_score(payloads: list[dict], window_games: int = 5) -> dict | None:
    """Compute form score from the most recent N snapshot payloads.

    Algorithm (0-100 scale):
        form_score = 50 * clamp(avg_rating / 10, 0, 1) + 50 * clamp(ga_per90 / 1.0, 0, 1)
    If no avg_rating available:
        form_score = 100 * clamp(ga_per90 / 1.0, 0, 1)
    """
    if not payloads:
        return None

    recent = payloads[:window_games]
    metrics = [_extract_metrics(p) for p in recent]

    total_minutes = sum(m["minutes"] for m in metrics)
    total_goals = sum(m["goals"] for m in metrics)
    total_assists = sum(m["assists"] for m in metrics)
    ratings = [m["avg_rating"] for m in metrics if m["avg_rating"] is not None]

    avg_rating = sum(ratings) / len(ratings) if ratings else None
    ga_per90 = (total_goals + total_assists) / max(total_minutes, 1) * 90

    if avg_rating is None:
        form_score = 100.0 * clamp(ga_per90 / 1.0, 0.0, 1.0)
    else:
        form_score = (
            50.0 * clamp(avg_rating / 10.0, 0.0, 1.0)
            + 50.0 * clamp(ga_per90 / 1.0, 0.0, 1.0)
        )

    return {
        "form_score": Decimal(str(round(clamp(form_score, 0.0, 100.0), 2))),
        "avg_rating": Decimal(str(round(avg_rating, 2))) if avg_rating is not None else None,
        "goals": total_goals,
        "assists": total_assists,
        "minutes": total_minutes,
        "games_considered": len(recent),
        "key_metrics": {"ga_per90": round(ga_per90, 4)},
    }


def compute_trend(payloads: list[dict], window_games: int = 5) -> Decimal | None:
    """trend = current_window_score - previous_window_score, or None if not enough data."""
    if len(payloads) < window_games * 2:
        return None
    current = compute_form_score(payloads[:window_games], window_games)
    previous = compute_form_score(payloads[window_games: window_games * 2], window_games)
    if current is None or previous is None:
        return None
    return Decimal(str(round(float(current["form_score"]) - float(previous["form_score"]), 2)))
