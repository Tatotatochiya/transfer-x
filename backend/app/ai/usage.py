"""In-memory AI usage tracker — resets on server restart."""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field

# Estimated cost per 1M tokens in USD (approximate mid-2025 pricing)
_COST_PER_1M: dict[str, dict[str, float]] = {
    "anthropic": {"input": 3.0,   "output": 15.0},
    "openai":    {"input": 5.0,   "output": 15.0},
    "deepseek":  {"input": 0.14,  "output": 0.28},
}


@dataclass
class UsageEntry:
    user_id: str
    endpoint: str
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float
    timestamp: float = field(default_factory=time.time)


_entries: list[UsageEntry] = []


def record(
    user_id: uuid.UUID,
    endpoint: str,
    prompt_tokens: int,
    completion_tokens: int,
    provider: str,
) -> None:
    rates = _COST_PER_1M.get(provider, {"input": 0.0, "output": 0.0})
    cost = (prompt_tokens / 1_000_000) * rates["input"] + (
        completion_tokens / 1_000_000
    ) * rates["output"]
    _entries.append(
        UsageEntry(
            user_id=str(user_id),
            endpoint=endpoint,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=cost,
        )
    )


def get_stats() -> dict:
    total_cost = sum(e.cost_usd for e in _entries)
    by_endpoint: dict[str, dict] = {}
    for e in _entries:
        ep = by_endpoint.setdefault(e.endpoint, {"requests": 0, "cost_usd": 0.0})
        ep["requests"] += 1
        ep["cost_usd"] = round(ep["cost_usd"] + e.cost_usd, 6)

    return {
        "total_requests": len(_entries),
        "total_prompt_tokens": sum(e.prompt_tokens for e in _entries),
        "total_completion_tokens": sum(e.completion_tokens for e in _entries),
        "total_cost_usd": round(total_cost, 4),
        "by_endpoint": by_endpoint,
        "note": "Stats are in-memory and reset on server restart.",
    }
