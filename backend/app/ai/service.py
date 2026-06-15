"""AI feature services — orchestrate context assembly, LLM calls, and caching."""
from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from typing import AsyncGenerator

import litellm
from sqlalchemy import nullslast, select

from app.ai.client import _detect_provider, _resolve_api_key, chat
from app.ai.context import build_market_context, build_player_context, build_shortlist_context, build_squad_context
from app.ai.prompts import (
    get_prompt,
    MARKET_RECOMMENDATIONS_USER,
    NL_SEARCH_PARSE,
    PLAYER_FIT_USER,
    SHORTLIST_REVIEW_USER,
    SQUAD_ANALYSIS_USER,
)
from app.ai.schemas import (
    MarketRecommendationsResponse,
    NLPlayerSearchResult,
    NLSearchResponse,
    ParsedFilters,
    PlayerFitResponse,
    PlayerRecommendation,
    RecommendedProfile,
    ShortlistPlayerAssessment,
    ShortlistReviewResponse,
    SquadAnalysisResponse,
)
from app.config import settings
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# ── Helpers ────────────────────────────────────────────────────────────────────

def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.rsplit("```", 1)[0].strip()
    return text


def _parse_squad_analysis(text: str) -> SquadAnalysisResponse:
    data = json.loads(_strip_fences(text))
    return SquadAnalysisResponse(
        summary=data.get("summary", ""),
        positional_gaps=data.get("positional_gaps", []),
        age_risks=data.get("age_risks", []),
        contract_risks=data.get("contract_risks", []),
        recommended_profiles=[
            RecommendedProfile(**p) for p in data.get("recommended_profiles", [])
        ],
        cached=False,
    )


# ── Squad Analysis ─────────────────────────────────────────────────────────────

_SQUAD_CACHE_TTL = 3600
_squad_cache: dict[str, tuple[float, SquadAnalysisResponse]] = {}


async def analyse_squad(
    db: AsyncSession,
    club_id: uuid.UUID,
    user_id: uuid.UUID | None = None,
    force_refresh: bool = False,
) -> SquadAnalysisResponse:
    cache_key = str(club_id)
    if not force_refresh:
        cached = _squad_cache.get(cache_key)
        if cached and time.monotonic() - cached[0] < _SQUAD_CACHE_TTL:
            result = cached[1].model_copy()
            result.cached = True
            return result

    squad_data = await build_squad_context(db, club_id)
    if not squad_data:
        raise ValueError(f"Club {club_id} not found")

    messages = [
        {"role": "system", "content": get_prompt("SYSTEM_SCOUT")},
        {
            "role": "user",
            "content": get_prompt("SQUAD_ANALYSIS_USER").format(
                squad_json=json.dumps(squad_data, indent=2)
            ),
        },
    ]

    raw = await chat(messages, user_id=user_id, endpoint="squad-analysis")
    result = _parse_squad_analysis(raw)
    _squad_cache[cache_key] = (time.monotonic(), result)
    return result


async def stream_squad_analysis(
    squad_data: dict,
    club_id: uuid.UUID,
    user_id: uuid.UUID | None = None,
) -> AsyncGenerator[str, None]:
    """Async generator yielding SSE-formatted chunks then a final done event."""
    messages = [
        {"role": "system", "content": get_prompt("SYSTEM_SCOUT")},
        {
            "role": "user",
            "content": get_prompt("SQUAD_ANALYSIS_USER").format(
                squad_json=json.dumps(squad_data, indent=2)
            ),
        },
    ]

    full_text = ""
    prompt_tokens = 0
    completion_tokens = 0

    try:
        response = await litellm.acompletion(
            model=settings.llm_model,
            messages=messages,
            api_key=_resolve_api_key(),
            stream=True,
        )

        async for chunk in response:
            content = chunk.choices[0].delta.content or ""
            if content:
                full_text += content
                yield f"data: {json.dumps({'type': 'chunk', 'content': content})}\n\n"
            # Capture usage from the final chunk if provided
            if hasattr(chunk, "usage") and chunk.usage:
                prompt_tokens = chunk.usage.prompt_tokens or 0
                completion_tokens = chunk.usage.completion_tokens or 0

        result = _parse_squad_analysis(full_text)
        _squad_cache[str(club_id)] = (time.monotonic(), result)

        if user_id is not None and (prompt_tokens or completion_tokens):
            from app.ai.usage import record
            record(
                user_id=user_id,
                endpoint="squad-analysis-stream",
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                provider=_detect_provider(),
            )

        yield f"data: {json.dumps({'type': 'done', 'result': result.model_dump()})}\n\n"
        yield "data: [DONE]\n\n"

    except Exception as exc:
        logger.exception("Error in stream_squad_analysis")
        yield f"data: {json.dumps({'type': 'error', 'detail': str(exc)})}\n\n"


# ── Player Fit ─────────────────────────────────────────────────────────────────

_FIT_CACHE_TTL = 3600
_fit_cache: dict[str, tuple[float, PlayerFitResponse]] = {}


async def assess_player_fit(
    db: AsyncSession,
    player_id: uuid.UUID,
    club_id: uuid.UUID,
    user_id: uuid.UUID | None = None,
    force_refresh: bool = False,
) -> PlayerFitResponse:
    cache_key = f"{player_id}:{club_id}"
    if not force_refresh:
        cached = _fit_cache.get(cache_key)
        if cached and time.monotonic() - cached[0] < _FIT_CACHE_TTL:
            result = cached[1].model_copy()
            result.cached = True
            return result

    player_data, squad_data = await asyncio.gather(
        build_player_context(db, player_id),
        build_squad_context(db, club_id),
    )
    if not player_data:
        raise ValueError(f"Player {player_id} not found")
    if not squad_data:
        raise ValueError(f"Club {club_id} not found")

    messages = [
        {"role": "system", "content": get_prompt("SYSTEM_SCOUT")},
        {
            "role": "user",
            "content": get_prompt("PLAYER_FIT_USER").format(
                player_json=json.dumps(player_data, indent=2),
                squad_json=json.dumps(squad_data, indent=2),
            ),
        },
    ]

    raw = await chat(messages, user_id=user_id, endpoint="player-fit")
    data = json.loads(_strip_fences(raw))

    result = PlayerFitResponse(
        fit_score=int(data.get("fit_score", 0)),
        summary=data.get("summary", ""),
        strengths=data.get("strengths", []),
        concerns=data.get("concerns", []),
        cached=False,
    )
    _fit_cache[cache_key] = (time.monotonic(), result)
    return result


# ── Market Recommendations ─────────────────────────────────────────────────────

_RECS_CACHE_TTL = 1800
_recs_cache: dict[str, tuple[float, MarketRecommendationsResponse]] = {}


async def recommend_market_players(
    db: AsyncSession,
    club_id: uuid.UUID,
    user_id: uuid.UUID | None = None,
    position: str | None = None,
    max_budget: int | None = None,
    min_age: int | None = None,
    max_age: int | None = None,
    force_refresh: bool = False,
) -> MarketRecommendationsResponse:
    cache_key = f"{club_id}:{position}:{max_budget}:{min_age}:{max_age}"
    if not force_refresh:
        cached = _recs_cache.get(cache_key)
        if cached and time.monotonic() - cached[0] < _RECS_CACHE_TTL:
            result = cached[1].model_copy()
            result.cached = True
            return result

    squad_data, market_data = await asyncio.gather(
        build_squad_context(db, club_id),
        build_market_context(db, club_id, position=position, max_budget=max_budget, min_age=min_age, max_age=max_age),
    )
    if not squad_data:
        raise ValueError(f"Club {club_id} not found")

    if not market_data:
        return MarketRecommendationsResponse(recommendations=[], total_candidates=0, cached=False)

    messages = [
        {"role": "system", "content": get_prompt("SYSTEM_SCOUT")},
        {
            "role": "user",
            "content": get_prompt("MARKET_RECOMMENDATIONS_USER").format(
                squad_json=json.dumps(squad_data, indent=2),
                market_json=json.dumps(market_data, indent=2),
            ),
        },
    ]

    raw = await chat(messages, user_id=user_id, endpoint="recommendations")
    items = json.loads(_strip_fences(raw))
    if not isinstance(items, list):
        items = items.get("recommendations", [])

    market_by_player: dict[str, dict] = {m["player_id"]: m for m in market_data}
    recommendations = []
    for item in items:
        pid = str(item.get("player_id", ""))
        market_entry = market_by_player.get(pid, {})
        recommendations.append(
            PlayerRecommendation(
                player_id=pid,
                sale_id=item.get("sale_id") or market_entry.get("sale_id"),
                name=item.get("name") or market_entry.get("name", ""),
                position=item.get("position") or market_entry.get("position"),
                fit_score=int(item.get("fit_score", 0)),
                reason=item.get("reason", ""),
            )
        )

    result = MarketRecommendationsResponse(
        recommendations=recommendations,
        total_candidates=len(market_data),
        cached=False,
    )
    _recs_cache[cache_key] = (time.monotonic(), result)
    return result


# ── Natural Language Player Search ─────────────────────────────────────────────

async def nl_player_search(
    db: AsyncSession,
    query: str,
    user_id: uuid.UUID | None = None,
) -> NLSearchResponse:
    """Parse a natural language query into filters, then execute a DB search."""
    from app.clubs.models import Club
    from app.players.models import Player, PlayerPosition
    from app.stats.models import PlayerForm

    # Step 1: LLM parses the query into structured filters
    messages = [
        {"role": "system", "content": get_prompt("SYSTEM_SCOUT")},
        {"role": "user", "content": get_prompt("NL_SEARCH_PARSE").format(query=query)},
    ]
    raw = await chat(messages, user_id=user_id, endpoint="player-search")
    data = json.loads(_strip_fences(raw))

    parsed = ParsedFilters(
        position=data.get("position"),
        min_age=data.get("min_age"),
        max_age=data.get("max_age"),
        min_form_score=data.get("min_form_score"),
        nationalities=data.get("nationalities") or None,
        min_height_cm=data.get("min_height_cm"),
        open_to_offers=data.get("open_to_offers"),
        interpreted_as=data.get("interpreted_as", query),
    )

    # Step 2: Build DB query from parsed filters
    stmt = (
        select(Player, PlayerForm, Club)
        .outerjoin(PlayerForm, PlayerForm.player_id == Player.id)
        .outerjoin(Club, Club.id == Player.current_club_id)
    )

    if parsed.position:
        try:
            stmt = stmt.where(Player.position == PlayerPosition(parsed.position))
        except ValueError:
            pass
    if parsed.min_age is not None:
        stmt = stmt.where(Player.age >= parsed.min_age)
    if parsed.max_age is not None:
        stmt = stmt.where(Player.age <= parsed.max_age)
    if parsed.nationalities:
        from sqlalchemy import or_
        nat_filters = [Player.nationality.ilike(f"%{n}%") for n in parsed.nationalities]
        stmt = stmt.where(or_(*nat_filters))
    if parsed.min_height_cm is not None:
        from sqlalchemy import Integer, cast, func
        numeric_height = cast(func.regexp_replace(Player.height, r"[^0-9]", "", "g"), Integer)
        stmt = stmt.where(
            Player.height.isnot(None),
            Player.height != "",
            numeric_height >= parsed.min_height_cm,
        )
    if parsed.open_to_offers:
        stmt = stmt.where(Player.open_to_offers == True)  # noqa: E712
    if parsed.min_form_score is not None:
        stmt = stmt.where(PlayerForm.form_score >= parsed.min_form_score)

    stmt = stmt.order_by(nullslast(PlayerForm.form_score.desc())).limit(20)

    rows = (await db.execute(stmt)).all()

    players = [
        NLPlayerSearchResult(
            player_id=str(p.id),
            name=p.name,
            age=p.age,
            position=p.position.value if p.position else None,
            nationality=p.nationality,
            current_club=club.name if club else None,
            form_score=float(form.form_score) if form else None,
            open_to_offers=p.open_to_offers,
        )
        for p, form, club in rows
    ]

    return NLSearchResponse(players=players, filters=parsed, total=len(players))


# ── Shortlist Review ───────────────────────────────────────────────────────────

_SHORTLIST_CACHE_TTL = 1800
_shortlist_cache: dict[str, tuple[float, ShortlistReviewResponse]] = {}


async def review_shortlist(
    db: AsyncSession,
    shortlist_id: uuid.UUID,
    club_id: uuid.UUID,
    user_id: uuid.UUID | None = None,
    force_refresh: bool = False,
) -> ShortlistReviewResponse:
    cache_key = str(shortlist_id)
    if not force_refresh:
        cached = _shortlist_cache.get(cache_key)
        if cached and time.monotonic() - cached[0] < _SHORTLIST_CACHE_TTL:
            result = cached[1].model_copy()
            result.cached = True
            return result

    shortlist_data, squad_data = await asyncio.gather(
        build_shortlist_context(db, shortlist_id),
        build_squad_context(db, club_id),
    )
    if not shortlist_data:
        raise ValueError(f"Shortlist {shortlist_id} not found")
    if not shortlist_data.get("items"):
        raise ValueError("Shortlist is empty")

    messages = [
        {"role": "system", "content": get_prompt("SYSTEM_SCOUT")},
        {
            "role": "user",
            "content": get_prompt("SHORTLIST_REVIEW_USER").format(
                squad_json=json.dumps(squad_data, indent=2),
                shortlist_json=json.dumps(shortlist_data, indent=2),
            ),
        },
    ]

    raw = await chat(messages, user_id=user_id, endpoint="shortlist-review")
    data = json.loads(_strip_fences(raw))

    result = ShortlistReviewResponse(
        summary=data.get("summary", ""),
        overall_verdict=data.get("overall_verdict", "adequate"),
        player_assessments=[
            ShortlistPlayerAssessment(**a) for a in data.get("player_assessments", [])
        ],
        top_picks=data.get("top_picks", []),
        missing_positions=data.get("missing_positions", []),
        cached=False,
    )
    _shortlist_cache[cache_key] = (time.monotonic(), result)
    return result
