"""AI feature router — mounted at /ai."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.client import _detect_provider
from app.ai.rate_limit import check_rate_limit, get_rate_limit_status
from app.ai.schemas import (
    AIConfigResponse,
    AIRateLimitStatus,
    AIUsageStats,
    MarketRecommendationsResponse,
    NLSearchRequest,
    NLSearchResponse,
    PlayerFitResponse,
    PromptInfo,
    PromptOverrideRequest,
    ShortlistReviewResponse,
    SquadAnalysisResponse,
)
from app.auth.models import User
from app.config import settings
from app.database import get_db
from app.deps import get_current_superuser, get_current_user

router = APIRouter(prefix="/ai", tags=["ai"])


def _require_llm_key() -> None:
    if not any([settings.anthropic_api_key, settings.openai_api_key, settings.deepseek_api_key]):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No LLM API key configured",
        )


async def _get_club(db: AsyncSession, user: User):
    from app.clubs import service as clubs_service
    club = await clubs_service.get_club_for_user(db, user.id)
    if club is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No club found for this user")
    return club


# ── Config ─────────────────────────────────────────────────────────────────────

@router.get("/config", response_model=AIConfigResponse)
async def get_ai_config(current_user: User = Depends(get_current_superuser)) -> AIConfigResponse:
    """Return active LLM provider and key configuration status. Superuser only."""
    return AIConfigResponse(
        model=settings.llm_model,
        provider=_detect_provider(),
        anthropic_configured=bool(settings.anthropic_api_key),
        openai_configured=bool(settings.openai_api_key),
        deepseek_configured=bool(settings.deepseek_api_key),
    )


# ── Rate limit status ──────────────────────────────────────────────────────────

@router.get("/rate-limit", response_model=AIRateLimitStatus)
async def rate_limit_status(
    current_user: User = Depends(get_current_user),
) -> AIRateLimitStatus:
    """Return the current user's AI rate limit usage."""
    return AIRateLimitStatus(**get_rate_limit_status(current_user.id))


# ── Squad Analysis ─────────────────────────────────────────────────────────────

@router.post("/squad-analysis", response_model=SquadAnalysisResponse)
async def squad_analysis(
    force_refresh: bool = Query(False),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SquadAnalysisResponse:
    """AI squad report — positional gaps, age/contract risks, transfer profiles. Cached 1 h."""
    from app.ai.service import analyse_squad
    _require_llm_key()
    check_rate_limit(current_user.id)
    club = await _get_club(db, current_user)
    try:
        return await analyse_squad(db, club.id, user_id=current_user.id, force_refresh=force_refresh)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"LLM error: {exc}")


@router.get("/squad-analysis/stream")
async def squad_analysis_stream(
    force_refresh: bool = Query(False),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """SSE stream of the squad analysis — tokens appear progressively, final event contains parsed result."""
    from app.ai.context import build_squad_context
    from app.ai.service import stream_squad_analysis, _squad_cache
    _require_llm_key()
    check_rate_limit(current_user.id)
    club = await _get_club(db, current_user)

    # Check cache before opening stream
    import time
    from app.ai.service import _SQUAD_CACHE_TTL
    if not force_refresh:
        cached = _squad_cache.get(str(club.id))
        if cached and time.monotonic() - cached[0] < _SQUAD_CACHE_TTL:
            import json
            result = cached[1].model_copy()
            result.cached = True
            async def cached_stream():
                yield f"data: {json.dumps({'type': 'done', 'result': result.model_dump()})}\n\n"
                yield "data: [DONE]\n\n"
            return StreamingResponse(cached_stream(), media_type="text/event-stream",
                                     headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    squad_data = await build_squad_context(db, club.id)
    if not squad_data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Club not found")

    return StreamingResponse(
        stream_squad_analysis(squad_data, club.id, user_id=current_user.id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Player Fit ─────────────────────────────────────────────────────────────────

@router.get("/player-fit/{player_id}", response_model=PlayerFitResponse)
async def player_fit(
    player_id: uuid.UUID,
    force_refresh: bool = Query(False),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PlayerFitResponse:
    """Score a player's fit against the requesting club's squad. Cached 1 h per player+club."""
    from app.ai.service import assess_player_fit
    _require_llm_key()
    check_rate_limit(current_user.id)
    club = await _get_club(db, current_user)
    try:
        return await assess_player_fit(db, player_id, club.id, user_id=current_user.id, force_refresh=force_refresh)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"LLM error: {exc}")


# ── Market Recommendations ─────────────────────────────────────────────────────

@router.get("/recommendations", response_model=MarketRecommendationsResponse)
async def market_recommendations(
    position: str | None = Query(None),
    max_budget: int | None = Query(None),
    min_age: int | None = Query(None),
    max_age: int | None = Query(None),
    force_refresh: bool = Query(False),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MarketRecommendationsResponse:
    """AI-ranked open-market recommendations tailored to your squad. Cached 30 min."""
    from app.ai.service import recommend_market_players
    _require_llm_key()
    check_rate_limit(current_user.id)
    club = await _get_club(db, current_user)
    try:
        return await recommend_market_players(
            db, club.id, user_id=current_user.id,
            position=position, max_budget=max_budget,
            min_age=min_age, max_age=max_age,
            force_refresh=force_refresh,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"LLM error: {exc}")


# ── Shortlist Review ──────────────────────────────────────────────────────────

@router.get("/shortlist-review/{shortlist_id}", response_model=ShortlistReviewResponse)
async def shortlist_review(
    shortlist_id: uuid.UUID,
    force_refresh: bool = Query(False),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ShortlistReviewResponse:
    """AI review of a shortlist — per-player assessments, top picks, missing positions."""
    from app.ai.service import review_shortlist
    _require_llm_key()
    check_rate_limit(current_user.id)
    club = await _get_club(db, current_user)
    try:
        return await review_shortlist(db, shortlist_id, club.id, user_id=current_user.id, force_refresh=force_refresh)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"LLM error: {exc}")


# ── Natural Language Player Search ────────────────────────────────────────────

@router.post("/player-search", response_model=NLSearchResponse)
async def nl_player_search(
    body: NLSearchRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NLSearchResponse:
    """Parse a natural language query into filters and return matching players."""
    from app.ai.service import nl_player_search as _search
    _require_llm_key()
    check_rate_limit(current_user.id)
    try:
        return await _search(db, body.query, user_id=current_user.id)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"LLM error: {exc}")


# ── Usage (admin) ──────────────────────────────────────────────────────────────

@router.get("/usage", response_model=AIUsageStats)
async def ai_usage(current_user: User = Depends(get_current_superuser)) -> AIUsageStats:
    """AI usage stats — total requests, tokens, estimated cost. Superuser only."""
    from app.ai.usage import get_stats
    return AIUsageStats(**get_stats())


# ── Prompt versioning (admin) ──────────────────────────────────────────────────

@router.get("/prompts", response_model=list[PromptInfo])
async def list_prompts(current_user: User = Depends(get_current_superuser)) -> list[PromptInfo]:
    """List all prompt templates with override status. Superuser only."""
    from app.ai.prompts import list_prompts as _list
    return [PromptInfo(**p) for p in _list()]


@router.put("/prompts/{key}", response_model=PromptInfo)
async def update_prompt(
    key: str,
    body: PromptOverrideRequest,
    current_user: User = Depends(get_current_superuser),
) -> PromptInfo:
    """Override a prompt template in memory. Resets on server restart. Superuser only."""
    from app.ai.prompts import set_override, list_prompts as _list
    try:
        set_override(key, body.content)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return PromptInfo(**next(p for p in _list() if p["key"] == key))


@router.delete("/prompts/{key}", status_code=status.HTTP_204_NO_CONTENT)
async def reset_prompt(
    key: str,
    current_user: User = Depends(get_current_superuser),
) -> None:
    """Reset a prompt override back to the built-in default. Superuser only."""
    from app.ai.prompts import reset_override
    reset_override(key)
