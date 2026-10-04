"""GDPR (Phase 1): a person can download their data and close their account.

Export is the person's own data: their account, profile, preferences,
devices, notifications, what they did (audit events) and what they wrote.
Club data (players, deals, finances) belongs to the club, not to them.

Closing an account erases the personal details and keeps the records a
dispute or an audit relies on: audit events, deal comments, negotiation
messages and terms versions stay, attributed to a closed account with no
name or email. The user row stays too (it's what those records point to),
inactive and anonymised, with `deleted_at` set (migration 0096).
"""
import secrets
import uuid
from datetime import datetime, timezone

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import AgentProfile, PlayerProfile, RefreshToken, User


def _iso(v):
    return v.isoformat() if hasattr(v, "isoformat") else v


def _row(obj, fields: list[str]) -> dict:
    out = {}
    for f in fields:
        v = getattr(obj, f, None)
        out[f] = _iso(getattr(v, "value", v))
    return out


async def export_user_data(db: AsyncSession, user: User) -> dict:
    from app.agents.models import NegotiationMessage
    from app.ai.models import AssistantQuery
    from app.audit.models import AuditEvent
    from app.auth.router import _device_label
    from app.clubs import service as clubs_service
    from app.deals.room_models import DealComment
    from app.lite.models import UserPreference
    from app.notifications.models import Notification, NotificationPreference, PushSubscription

    club, role = await clubs_service.get_club_and_role_for_user(db, user.id)
    agent = (await db.execute(select(AgentProfile).where(AgentProfile.user_id == user.id))).scalar_one_or_none()
    player = (await db.execute(select(PlayerProfile).where(PlayerProfile.user_id == user.id))).scalar_one_or_none()
    prefs = await db.get(UserPreference, user.id)

    async def rows(model, where, order):
        return (await db.execute(select(model).where(where).order_by(order))).scalars().all()

    return {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "about": "Your personal data on TransferX. Club data (players, deals, finances) belongs to the club.",
        "account": _row(user, ["id", "email", "first_name", "last_name", "user_type", "created_at", "last_active_at"]),
        "club": {"name": club.name, "role": role} if club else None,
        "agent_profile": _row(agent, ["display_name", "agency_name", "licence_no", "country", "verified", "created_at"]) if agent else None,
        "player_profile": _row(player, ["player_id", "verified", "created_at"]) if player else None,
        "preferences": _row(prefs, [
            "lite_mode", "text_scale", "push_your_move", "push_heads_up", "push_summary", "summary_local_time",
            "quiet_hours_enabled", "quiet_start", "quiet_end", "timezone", "push_hide_amounts",
        ]) if prefs else None,
        "notification_preferences": [
            _row(p, ["type", "enabled", "email_enabled", "push_enabled"])
            for p in await rows(NotificationPreference, NotificationPreference.user_id == user.id, NotificationPreference.type)
        ],
        "signed_in_devices": [
            {"device": _device_label(t.user_agent), "signed_in_at": _iso(t.signed_in_at or t.created_at),
             "last_used_at": _iso(t.last_used_at)}
            for t in await rows(RefreshToken, RefreshToken.user_id == user.id, RefreshToken.created_at)
        ],
        "phones_with_notifications": [
            _row(s, ["platform", "created_at"])
            for s in await rows(PushSubscription, PushSubscription.user_id == user.id, PushSubscription.created_at)
        ],
        "notifications": [
            _row(n, ["type", "message", "link", "is_read", "created_at"])
            for n in await rows(Notification, Notification.recipient_user_id == user.id, Notification.created_at)
        ],
        "your_activity": [
            _row(e, ["created_at", "action", "entity_type", "entity_id", "description"])
            for e in await rows(AuditEvent, AuditEvent.actor_user_id == user.id, AuditEvent.created_at)
        ],
        "deal_comments_you_wrote": [
            _row(c, ["created_at", "deal_id", "body"])
            for c in await rows(DealComment, DealComment.author_user_id == user.id, DealComment.created_at)
        ],
        "negotiation_messages_you_sent": [
            _row(m, ["created_at", "negotiation_id", "body"])
            for m in await rows(NegotiationMessage, NegotiationMessage.sender_user_id == user.id, NegotiationMessage.created_at)
        ],
        "assistant_questions": [
            _row(q, ["created_at", "question"])
            for q in await rows(AssistantQuery, AssistantQuery.user_id == user.id, AssistantQuery.created_at)
        ],
    }


class CannotClose(Exception):
    """Closing would take something with it that isn't only theirs."""


async def check_can_close(db: AsyncSession, user: User) -> None:
    from app.clubs.models import Club
    from app.mandates.models import Mandate, MandateStatus

    if user.is_superuser:
        raise CannotClose("TransferX staff accounts are closed by another admin.")
    if (await db.execute(select(Club.id).where(Club.user_id == user.id))).first():
        raise CannotClose(
            "You own your club's account, so closing it would close the club. "
            "Contact TransferX to hand the club to someone else or close it."
        )
    agent = (await db.execute(select(AgentProfile).where(AgentProfile.user_id == user.id))).scalar_one_or_none()
    if agent is not None and (await db.execute(select(Mandate.id).where(
        Mandate.agent_id == agent.id, Mandate.status == MandateStatus.ACTIVE,
    ))).first():
        raise CannotClose("You still represent players. End your mandates first, or contact TransferX.")


async def close_account(db: AsyncSession, user: User) -> None:
    """Erase the person's details; keep the records others rely on."""
    from app.ai.models import AISuggestionEvent, AssistantQuery
    from app.analytics.models import AnalyticsEvent
    from app.clubs.models import ClubStaff
    from app.lite.models import HeldAction, UserPreference
    from app.notifications.models import Notification, NotificationPreference, PushDelivery, PushSubscription

    await check_can_close(db, user)
    uid = user.id
    for model, col in (
        (RefreshToken, RefreshToken.user_id), (PushDelivery, PushDelivery.user_id),
        (PushSubscription, PushSubscription.user_id), (NotificationPreference, NotificationPreference.user_id),
        (Notification, Notification.recipient_user_id), (UserPreference, UserPreference.user_id),
        (HeldAction, HeldAction.user_id), (AssistantQuery, AssistantQuery.user_id),
        (ClubStaff, ClubStaff.user_id), (PlayerProfile, PlayerProfile.user_id),
    ):
        await db.execute(delete(model).where(col == uid))
    await db.execute(update(AnalyticsEvent).where(AnalyticsEvent.user_id == uid)
                     .values(user_id=None, ip_address=None, user_agent=None))
    await db.execute(update(AISuggestionEvent).where(AISuggestionEvent.user_id == uid).values(user_id=None))
    await db.execute(update(AgentProfile).where(AgentProfile.user_id == uid)
                     .values(display_name="Former agent", licence_no=None))

    user.email = f"closed-{uuid.uuid4().hex[:16]}@closed.invalid"
    user.first_name = user.last_name = None
    from app.auth.service import hash_password

    user.hashed_password = hash_password(secrets.token_urlsafe(32))
    user.is_active = False
    user.deleted_at = datetime.now(timezone.utc)
    await db.flush()
