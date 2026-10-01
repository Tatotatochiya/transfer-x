"""Which assistant suggestions are used, and which are ignored (app/ai/models.py).

A feature records SHOWN when it offers something the user can use, and the
action that uses it records USED. Callers commit.
"""
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.models import AISuggestionEvent

# Every feature that offers a usable suggestion, with the label the admin page shows.
FEATURES: dict[str, str] = {
    "counter_advisor": "Counter-offer advice",
    "listing_assistant": "Listing guide price",
    "draft_deal_message": "Draft: deal room message",
    "draft_counter_note": "Draft: counter-offer note",
    "draft_enquiry_reply": "Draft: enquiry reply",
    "ask_proposal": "Ask: suggested action",
}

SHOWN, USED = "SHOWN", "USED"


async def record_shown(db: AsyncSession, feature: str, user_id: uuid.UUID, ref: str | uuid.UUID | None = None) -> None:
    """Once per user, feature and subject a day: a cached answer seen again
    is the same suggestion, not a new one."""
    ref = str(ref) if ref is not None else None
    since = datetime.now(timezone.utc) - timedelta(days=1)
    seen = (await db.execute(
        select(AISuggestionEvent.id).where(
            AISuggestionEvent.feature == feature, AISuggestionEvent.event == SHOWN,
            AISuggestionEvent.user_id == user_id,
            AISuggestionEvent.ref.is_(None) if ref is None else AISuggestionEvent.ref == ref,
            AISuggestionEvent.created_at >= since,
        ).limit(1)
    )).scalar_one_or_none()
    if seen is None:
        db.add(AISuggestionEvent(feature=feature, event=SHOWN, user_id=user_id, ref=ref))
        await db.flush()


async def record_used(db: AsyncSession, feature: str, user_id: uuid.UUID, ref: str | uuid.UUID | None = None) -> None:
    db.add(AISuggestionEvent(feature=feature, event=USED, user_id=user_id,
                             ref=str(ref) if ref is not None else None))
    await db.flush()


async def suggestion_stats(db: AsyncSession, days: int = 30) -> list[dict]:
    """Per feature over the last `days`: how often a suggestion was shown and
    used, and the share used. Features with no events still appear, at zero."""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows = (await db.execute(
        select(AISuggestionEvent.feature, AISuggestionEvent.event, func.count())
        .where(AISuggestionEvent.created_at >= since)
        .group_by(AISuggestionEvent.feature, AISuggestionEvent.event)
    )).all()
    counts: dict[str, dict[str, int]] = {}
    for feature, event, n in rows:
        counts.setdefault(feature, {})[event] = n
    out = []
    for feature in list(FEATURES) + [f for f in counts if f not in FEATURES]:
        shown = counts.get(feature, {}).get(SHOWN, 0)
        used = counts.get(feature, {}).get(USED, 0)
        out.append({
            "feature": feature, "label": FEATURES.get(feature, feature),
            "shown": shown, "used": used,
            "used_pct": round(100 * min(used, shown) / shown) if shown else None,
        })
    return out
