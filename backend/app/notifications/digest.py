"""Daily "waiting on you" digest email.

Clubs use TransferX a few times a week, not daily, and in-app notifications
alone let a seven-day offer expire unseen. Once a day each person who acts for
a club — the owner, Sporting Directors and Managers, the same people
role-routed club notifications reach — gets one email listing what is waiting
on them: the dashboard's tier-1 list, so the email and the dashboard never
disagree.

- Sent only when there is something waiting. A quiet day sends nothing.
- Sent at most once per UTC day, recorded on the user
  (`last_digest_sent_at`), because the scheduler re-runs jobs shortly after
  every start.
- Not before `DIGEST_HOUR_UTC`, so it arrives as a morning summary.
- Switched off from the notification preferences page (`DAILY_DIGEST`): either
  toggle off stops it.
- Without SMTP configured the send is skipped by `_send_sync`, and the user is
  still stamped: the digest for that day was produced, just not deliverable.
"""

import asyncio
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.notifications.email import _send_sync, render_digest_html
from app.notifications.models import NotificationPreference, NotificationType

logger = logging.getLogger(__name__)

DIGEST_HOUR_UTC = 7

def _line(item) -> str:
    """One row of the digest, from a dashboard item: who, and what is needed.
    The reason already names the kind ("Offer received — awaiting your
    response"), so it is not repeated."""
    who = " · ".join(x for x in (item.player_name, item.club_name) if x)
    return f"{who} — {item.reason}" if who else item.reason


async def _wants_digest(db: AsyncSession, user_id: uuid.UUID) -> bool:
    pref = (await db.execute(
        select(NotificationPreference).where(
            NotificationPreference.user_id == user_id,
            NotificationPreference.type == NotificationType.DAILY_DIGEST,
        )
    )).scalar_one_or_none()
    return pref is None or (pref.enabled and pref.email_enabled)


async def send_daily_digests(db: AsyncSession, *, now: datetime | None = None) -> int:
    """Send today's digest to everyone due one. Returns how many were sent."""
    from app.auth.models import User
    from app.clubs.models import Club
    from app.dashboard import service as dashboard_service
    from app.notifications.service import club_recipient_user_ids

    now = now or datetime.now(timezone.utc)
    if now.hour < DIGEST_HOUR_UTC:
        return 0
    today = now.date()

    sent = 0
    clubs = (await db.execute(select(Club))).scalars().all()
    for club in clubs:
        for user_id in await club_recipient_user_ids(db, club.id, NotificationType.DAILY_DIGEST):
            user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
            if user is None or not user.is_active or not user.email:
                continue
            last = user.last_digest_sent_at
            if last is not None:
                if last.tzinfo is None:  # SQLite drops tzinfo
                    last = last.replace(tzinfo=timezone.utc)
                if last.date() >= today:
                    continue
            if not await _wants_digest(db, user.id):
                continue

            items = (await dashboard_service.get_dashboard(db, club=club, current_user=user)).waiting_on_you
            if not items:
                continue

            # The AI briefing is a bonus: without a model, or if it fails or is
            # slow, the digest goes out exactly as before.
            briefing = None
            try:
                from app.ai.assist import club_briefing

                briefing = await asyncio.wait_for(club_briefing(db, club, user), timeout=30)
            except Exception:
                logger.warning("No AI briefing for user %s's digest", user.id)
            base = settings.frontend_base_url
            html_body = render_digest_html(
                [(_line(i), f"{base}{i.link}") for i in items],
                f"{base}/dashboard",
                briefing=briefing,
            )
            subject = (
                f"{len(items)} {'thing' if len(items) == 1 else 'things'} waiting on you — TransferX"
            )
            try:
                await asyncio.to_thread(_send_sync, user.email, subject, html_body)
            except Exception:
                # One bad address must not stop everyone else's digest; it is
                # not stamped, so the next run tries again.
                logger.exception("Daily digest failed for user %s", user.id)
                continue
            user.last_digest_sent_at = now
            await db.commit()
            sent += 1
    return sent
