"""LiteLLM wrapper — provider-agnostic chat completion."""
from __future__ import annotations

import uuid

import litellm

from app.config import settings

litellm.suppress_debug_info = True


def _resolve_api_key() -> str | None:
    m = settings.llm_model.lower()
    if "claude" in m or "anthropic" in m:
        return settings.anthropic_api_key
    if "gpt" in m or "openai" in m:
        return settings.openai_api_key
    if "deepseek" in m:
        return settings.deepseek_api_key
    return None


def _detect_provider() -> str:
    m = settings.llm_model.lower()
    if "claude" in m or "anthropic" in m:
        return "anthropic"
    if "gpt" in m or "openai" in m:
        return "openai"
    if "deepseek" in m:
        return "deepseek"
    return "unknown"


async def chat(
    messages: list[dict],
    user_id: uuid.UUID | None = None,
    endpoint: str = "unknown",
    **kwargs,
) -> str:
    """Send messages to the configured LLM and return the response text."""
    response = await litellm.acompletion(
        model=settings.llm_model,
        messages=messages,
        api_key=_resolve_api_key(),
        **kwargs,
    )

    if user_id is not None and response.usage:
        from app.ai.usage import record
        record(
            user_id=user_id,
            endpoint=endpoint,
            prompt_tokens=response.usage.prompt_tokens or 0,
            completion_tokens=response.usage.completion_tokens or 0,
            provider=_detect_provider(),
        )

    return response.choices[0].message.content
