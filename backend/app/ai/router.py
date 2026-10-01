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
from app.ai import models as _ai_models  # noqa: F401  (registers the AI tables)
from sqlalchemy import Integer

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
        return await _search(db, body.query, user_id=current_user.id, buyable=body.buyable)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"LLM error: {exc}")


# ── Usage (admin) ──────────────────────────────────────────────────────────────

@router.get("/usage", response_model=AIUsageStats)
async def ai_usage(current_user: User = Depends(get_current_superuser)) -> AIUsageStats:
    """AI usage stats — total requests, tokens, estimated cost. Superuser only."""
    from app.ai.usage import get_stats
    return AIUsageStats(**get_stats())


@router.get("/suggestions/stats")
async def suggestion_stats(
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Per feature: suggestions shown, used, and the share used. Superuser only."""
    from app.ai.tracking import suggestion_stats as _stats
    return {"days": days, "features": await _stats(db, days)}


@router.get("/assistant/questions")
async def assistant_questions(
    fallback_only: bool = Query(True),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Recent Ask questions, by default the ones it couldn't answer: they
    show what to build next. Superuser only."""
    from sqlalchemy import func, select

    from app.ai.models import AssistantQuery

    q = select(AssistantQuery).order_by(AssistantQuery.created_at.desc()).limit(limit)
    if fallback_only:
        q = q.where(AssistantQuery.fallback.is_(True))
    rows = (await db.execute(q)).scalars().all()
    totals = (await db.execute(select(func.count(), func.sum(func.cast(AssistantQuery.fallback, Integer))))).one()
    return {
        "total": totals[0] or 0, "fallbacks": int(totals[1] or 0),
        "questions": [{"question": r.question, "input": r.input, "lite": r.lite, "had_proposal": r.had_proposal,
                       "fallback": r.fallback, "created_at": r.created_at.isoformat()} for r in rows],
    }


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


# ── Workflow assistant (ai/assist.py) ─────────────────────────────────────────
#
# Every route resolves the caller's club and lets assist.py scope the facts to
# what that club may see. Nothing here changes state. The terms checker and a
# deal's next steps need no model; the rest answer 503 without one.


def _assist_errors(exc: Exception) -> HTTPException:
    if isinstance(exc, HTTPException):
        return exc
    if isinstance(exc, LookupError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    import logging
    logging.getLogger(__name__).warning("Assistant error: %s", exc)
    return HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail="The assistant could not answer just now — try again in a moment.",
    )


@router.get("/status")
async def assistant_status(current_user: User = Depends(get_current_user)) -> dict:
    """Whether AI answers are available — the UI hides AI buttons otherwise."""
    from app.ai.assist import ai_available
    from app.ai.rate_limit import get_rate_limit_status
    return {"available": ai_available(), "rate_limit": get_rate_limit_status(current_user.id)}


@router.post("/offer-check")
async def offer_check(
    body: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Rule-based warnings on draft offer terms (as the buyer) or on a counter
    or incoming offer (`offer_id`: the caller's side comes from the offer)."""
    from app.ai import assist
    club = await _get_club(db, current_user)
    terms = body.get("terms") or {}
    try:
        offer = None
        if body.get("offer_id"):
            offer = await assist._load_offer(db, uuid.UUID(str(body["offer_id"])), club.id)
        elif not terms.get("player_id"):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="player_id is required")
        return await assist.check_offer_terms(
            db, viewer_club_id=club.id, terms=terms, offer=offer, user=current_user, club=club,
        )
    except Exception as exc:
        raise _assist_errors(exc)


@router.get("/offers/{offer_id}/advice")
async def offer_advice(
    offer_id: uuid.UUID,
    refresh: bool = Query(False),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Counter-offer advisor for either party."""
    from app.ai.assist import offer_advice as _advice
    _require_llm_key()
    club = await _get_club(db, current_user)
    try:
        result = await _advice(db, offer_id, viewer_club_id=club.id, user_id=current_user.id, refresh=refresh)
    except Exception as exc:
        raise _assist_errors(exc)
    if result.get("suggested_terms"):
        from app.ai import tracking
        await tracking.record_shown(db, "counter_advisor", current_user.id, ref=offer_id)
        await db.commit()
    return result


@router.get("/offers/{offer_id}/summary")
async def offer_summary(
    offer_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from app.ai.assist import negotiation_summary
    _require_llm_key()
    club = await _get_club(db, current_user)
    try:
        return await negotiation_summary(db, offer_id, viewer_club_id=club.id, user_id=current_user.id)
    except Exception as exc:
        raise _assist_errors(exc)


@router.get("/deals/{deal_id}/next-steps")
async def deal_next_steps(
    deal_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """What the deal waits on and who must act; plus an AI brief when available."""
    from app.ai.assist import deal_next_steps as _steps
    club = await _get_club(db, current_user)
    try:
        return await _steps(db, deal_id, viewer_club_id=club.id, user_id=current_user.id)
    except Exception as exc:
        raise _assist_errors(exc)


@router.get("/briefing")
async def briefing(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict | None:
    """Today's briefing for the caller, or null without a model."""
    from app.ai.assist import club_briefing
    club = await _get_club(db, current_user)
    try:
        return await club_briefing(db, club, current_user)
    except Exception as exc:
        raise _assist_errors(exc)


@router.get("/listing-advice/{player_id}")
async def listing_advice(
    player_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Guide price (model + comparable transfers) and availability for one of
    the caller's own players. The guide price needs no model."""
    from app.ai.assist import listing_advice as _advice
    club = await _get_club(db, current_user)
    try:
        result = await _advice(db, player_id, viewer_club_id=club.id, user_id=current_user.id)
    except Exception as exc:
        raise _assist_errors(exc)
    if result.get("guide_price"):
        from app.ai import tracking
        await tracking.record_shown(db, "listing_assistant", current_user.id, ref=player_id)
        await db.commit()
    return result


@router.get("/potential-buyers/{player_id}")
async def potential_buyers(
    player_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Clubs whose (public) squads suggest a need for one of the caller's players."""
    from app.ai.assist import potential_buyers as _buyers
    club = await _get_club(db, current_user)
    try:
        return await _buyers(db, player_id, viewer_club_id=club.id, user_id=current_user.id)
    except Exception as exc:
        raise _assist_errors(exc)


@router.post("/ask")
async def ask(
    body: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Ask TransferX: questions about the caller's own club, answered from its
    data. `lite: true` gives Lite's short answers, Lite links and checked
    `proposal`s; `input` ("text" | "voice") is only logged. In Lite, a model
    failure answers with the fallback (shortcuts only) rather than an error."""
    from app.ai.assist import LITE_PAGES
    from app.ai.assist import ask as _ask
    question = str(body.get("question") or "").strip()
    if len(question) < 3:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Ask a question")
    lite = bool(body.get("lite"))
    fallback = {"answer": None, "links": LITE_PAGES[1:3], "proposal": None, "fallback": True, "cached": False}
    if lite and not ai_available_now():
        return fallback
    _require_llm_key()
    club = await _get_club(db, current_user)
    try:
        result = await _ask(db, club, current_user, question, lite=lite, input=str(body.get("input") or "text"))
    except HTTPException:
        await db.commit()  # the question is logged even when it is refused
        raise
    except Exception as exc:
        await db.commit()
        if lite:
            return fallback
        raise _assist_errors(exc)
    await db.commit()
    return result


def ai_available_now() -> bool:
    from app.ai.assist import ai_available
    return ai_available()


# ── Drafts (the assistant writes; the user edits and sends) ───────────────────


@router.post("/draft")
async def draft(
    body: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """A draft deal-room message, offer note or enquiry reply, for the user to
    edit and send through the normal box. Nothing is sent from here."""
    from app.ai import tracking
    from app.ai.assist import DRAFT_KINDS, draft_message

    kind = str(body.get("kind") or "")
    if kind not in DRAFT_KINDS:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unknown draft kind")
    try:
        ref_id = uuid.UUID(str(body.get("id")))
    except ValueError:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="id is required")
    _require_llm_key()
    club = await _get_club(db, current_user)
    try:
        result = await draft_message(db, kind=kind, ref_id=ref_id, club=club, user=current_user,
                                     channel=body.get("channel"), intent=body.get("intent"))
    except Exception as exc:
        raise _assist_errors(exc)
    await tracking.record_shown(db, f"draft_{kind}", current_user.id, ref=ref_id)
    await db.commit()
    return result


@router.post("/suggestions/used", status_code=status.HTTP_204_NO_CONTENT)
async def suggestion_used(
    body: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """The page says a draft was sent (largely as written). Only drafts are
    reported this way; every other use is recorded by the action itself."""
    from app.ai import tracking

    feature = str(body.get("feature") or "")
    if not feature.startswith("draft_") or feature not in tracking.FEATURES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unknown feature")
    await tracking.record_used(db, feature, current_user.id, ref=str(body.get("ref") or "")[:100] or None)
    await db.commit()
