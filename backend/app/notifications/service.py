"""M5 — Notification service layer."""

import asyncio
import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.filters import apply_date_range
from app.notifications import push
from app.notifications.models import Notification, NotificationPreference, NotificationType


# ── Core helpers ──────────────────────────────────────────────────────────────


async def create_notification(
    db: AsyncSession,
    *,
    recipient_user_id: uuid.UUID,
    type: NotificationType,
    message: str,
    link: str | None = None,
    related_player_id: uuid.UUID | None = None,
    related_club_id: uuid.UUID | None = None,
    title: str | None = None,
    body: str | None = None,
    group_key: str | None = None,
    deadline_at: datetime | None = None,
    actions: list[dict] | None = None,
    once: bool = False,
) -> Notification | None:
    """Create an in-app notification, and fire its WebSocket refresh, email
    and phone push.

    `title`, `body`, `group_key`, `deadline_at` and `actions` shape the push
    (docs/feature_spec/mobile-notifications §3); all optional. With `once`,
    a notification already sent to this person of this type about this
    `group_key` means this one is skipped: the scheduled reminders use it so
    an hourly job tells each person once rather than every hour.
    """
    if once and group_key:
        already = await db.execute(
            select(Notification.id).where(
                Notification.recipient_user_id == recipient_user_id,
                Notification.type == type,
                Notification.group_key == group_key,
            ).limit(1)
        )
        if already.first() is not None:
            return None

    pref = await db.execute(
        select(NotificationPreference).where(
            NotificationPreference.user_id == recipient_user_id,
            NotificationPreference.type == type,
        )
    )
    pref_row = pref.scalar_one_or_none()
    if pref_row is not None and not pref_row.enabled:
        return None  # Suppressed by user preference
    if related_club_id is None:
        related_club_id = await _other_club(db, recipient_user_id, link)

    n = Notification(
        recipient_user_id=recipient_user_id,
        type=type,
        message=message,
        link=link,
        is_read=False,
        related_player_id=related_player_id,
        related_club_id=related_club_id,
        title=title[:120] if title else None,
        body=body[:240] if body else None,
        group_key=group_key,
        deadline_at=deadline_at,
        actions_json=actions[:2] if actions else None,
    )
    db.add(n)
    await db.flush()

    # Sent once the caller's transaction commits (push.queue_push).
    push.queue_push(db, n.id)

    # Push a WS event so the client can refresh the notification bell without polling
    from app.ws.manager import manager as ws_manager
    asyncio.create_task(
        ws_manager.send_to_user(
            recipient_user_id,
            {"type": "NOTIFICATION"},
        )
    )

    # TRA-44: fire-and-forget email for the curated set of high-value notification types
    email_enabled = pref_row.email_enabled if pref_row is not None else True
    if email_enabled:
        from app.notifications.email import EMAIL_ENABLED_TYPES, maybe_send_notification_email

        # Mobile notifications §6.3: if this "your move" will reach their
        # phone, the email waits 30 minutes and goes only if still unread
        # (push.send_email_fallbacks). Everyone else is emailed now, as before.
        if type in EMAIL_ENABLED_TYPES and await push.will_push(db, recipient_user_id, type, pref_row):
            n.email_due_at = datetime.now(timezone.utc) + push.EMAIL_FALLBACK_DELAY
        else:
            asyncio.create_task(
                maybe_send_notification_email(recipient_user_id, type, message, link)
            )

    return n


async def get_unread_count(db: AsyncSession, user_id: uuid.UUID) -> int:
    result = await db.execute(
        select(func.count())
        .select_from(Notification)
        .where(Notification.recipient_user_id == user_id, Notification.is_read == False)  # noqa: E712
    )
    return result.scalar_one()


# Letters with no Unicode decomposition, folded by hand.
_SPECIAL = {"ø": "o", "đ": "d", "ı": "i", "ł": "l"}


def _fold(text: str) -> str:
    """Lower case without accents, so "estev" finds Estêvão and "odeg" Ødegaard."""
    import unicodedata

    text = "".join(_SPECIAL.get(c, c) for c in text.lower())
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))


# For Postgres's translate(): each accented letter and its plain one, same length.
_ACCENTED = "áàâäãåāăąçćčďéèêëēėęěíìîïīįñńňóòôöõōőřśšşșťțúùûüūůűųýÿžźżøđıł"
_PLAIN = "".join(_fold(c) for c in _ACCENTED)
assert len(_ACCENTED) == len(_PLAIN)


def _folded(col, dialect: str | None):
    """A column lower-cased, and on Postgres stripped of accents too
    (translate); SQLite, in tests, only lower-cases."""
    lowered = func.lower(col)
    return func.translate(lowered, _ACCENTED, _PLAIN) if dialect == "postgresql" else lowered


def _filtered(q, *, unread: bool = False, tier: str | None = None, category: str | None = None,
              player_id: uuid.UUID | None = None, club_id: uuid.UUID | None = None, search: str | None = None,
              dialect: str | None = None):
    """The notifications page's filters, on a query over Notification. `search`
    matches the player's name, the club's name and the wording (so a club
    named only in the text still matches). Unknown tier or category: no rows."""
    from app.clubs.models import Club
    from app.notifications.tiers import CATEGORIES, TIERS
    from app.players.models import Player

    if unread:
        q = q.where(Notification.is_read == False)  # noqa: E712
    if tier:
        q = q.where(Notification.type.in_([t for t, v in TIERS.items() if v.value == tier] or [None]))
    if category:
        q = q.where(Notification.type.in_(list(CATEGORIES.get(category, set())) or [None]))
    if player_id:
        q = q.where(Notification.related_player_id == player_id)
    if club_id:
        q = q.where(Notification.related_club_id == club_id)
    needle = (search or "").strip()
    if needle:
        like = f"%{_fold(needle)}%"
        cols = (Player.name, Club.name, Notification.message, Notification.title, Notification.body)
        q = (q.outerjoin(Player, Player.id == Notification.related_player_id)
             .outerjoin(Club, Club.id == Notification.related_club_id)
             .where(or_(*(_folded(c, dialect).like(like) for c in cols))))
    return q


async def list_notifications(
    db: AsyncSession,
    user_id: uuid.UUID,
    date_from: date | None = None,
    date_to: date | None = None,
    page: int = 1,
    page_size: int = 30,
    **filters,
) -> tuple[list[Notification], int]:
    q = select(Notification).where(Notification.recipient_user_id == user_id)
    q = apply_date_range(q, Notification.created_at, date_from, date_to)
    q = _filtered(q, dialect=db.bind.dialect.name, **filters)
    total_result = await db.execute(select(func.count()).select_from(q.subquery()))
    total = total_result.scalar_one()
    rows = await db.execute(
        q.order_by(Notification.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(rows.scalars()), total


async def mark_read(db: AsyncSession, notification_id: uuid.UUID, user_id: uuid.UUID) -> Notification | None:
    result = await db.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.recipient_user_id == user_id,
        )
    )
    n = result.scalar_one_or_none()
    if n:
        n.is_read = True
        await db.flush()
    return n


async def mark_all_read(db: AsyncSession, user_id: uuid.UUID, date_from: date | None = None,
                        date_to: date | None = None, **filters) -> int:
    """Mark read every unread notification, or only those the page's filters
    show ("Mark these read")."""
    ids = select(Notification.id).where(Notification.recipient_user_id == user_id)
    ids = apply_date_range(ids, Notification.created_at, date_from, date_to)
    ids = _filtered(ids, unread=True, dialect=db.bind.dialect.name,
                    **{k: v for k, v in filters.items() if k != "unread"})
    result = await db.execute(
        update(Notification)
        .where(Notification.id.in_(ids.scalar_subquery()))
        .values(is_read=True)
        .execution_options(synchronize_session=False)
    )
    return result.rowcount


async def _other_club(db: AsyncSession, recipient_user_id: uuid.UUID, link: str | None) -> uuid.UUID | None:
    """For a notification about an offer or a deal, the other club in it (as
    the recipient sees it), so the page can show it and filter by it. Never an
    anonymous buyer before acceptance (common/masking)."""
    import re

    from app.clubs.service import get_club_for_user
    from app.common.masking import buyer_is_masked
    from app.deals.models import Deal
    from app.offers.models import Offer

    m = re.match(r"^/(offers|deals)/([0-9a-fA-F-]{36})", link or "")
    if not m:
        return None
    club = await get_club_for_user(db, recipient_user_id)
    if club is None:
        return None
    entity_id = uuid.UUID(m.group(2))
    if m.group(1) == "offers":
        offer = await db.get(Offer, entity_id)
        if offer is None or club.id not in (offer.from_club_id, offer.to_club_id):
            return None
        if club.id == offer.from_club_id:
            return offer.to_club_id
        return None if buyer_is_masked(offer, club.id) else offer.from_club_id
    deal = await db.get(Deal, entity_id)
    if deal is None or club.id not in (deal.buyer_club_id, deal.seller_club_id):
        return None
    return deal.seller_club_id if club.id == deal.buyer_club_id else deal.buyer_club_id


# ── Club recipient routing (TRA-152, D5) ─────────────────────────────────────

# Scouting/market events additionally reach SCOUT staff; everything else that
# is club-routed (deal, offer, bid, negotiation, instalment/clause events)
# reaches OWNER + SPORTING_DIRECTOR + MANAGER. Account/administrative events
# (verification, staff invitations) are owner-directed at their call sites and
# never routed through here.
_SCOUT_INCLUSIVE_TYPES: set[NotificationType] = {
    NotificationType.PLAYER_AVAILABLE,
}


async def club_recipient_user_ids(
    db: AsyncSession, club_id: uuid.UUID, notification_type: NotificationType
) -> list[uuid.UUID]:
    """Resolve a club-directed notification to every member who should get it —
    the owner plus staff filtered by the D5 role mapping. Per-user preference
    opt-outs still apply downstream in create_notification."""
    from app.clubs.models import Club, ClubStaff, StaffRole

    club_id = uuid.UUID(str(club_id))
    club_result = await db.execute(select(Club).where(Club.id == club_id))
    club = club_result.scalar_one_or_none()
    if club is None:
        return []

    roles = {StaffRole.SPORTING_DIRECTOR, StaffRole.MANAGER}
    if notification_type in _SCOUT_INCLUSIVE_TYPES:
        roles.add(StaffRole.SCOUT)

    staff_result = await db.execute(
        select(ClubStaff.user_id).where(ClubStaff.club_id == club_id, ClubStaff.role.in_(roles))
    )
    return [club.user_id] + [uuid.UUID(str(uid)) for uid in staff_result.scalars()]


async def notify_club(
    db: AsyncSession,
    club_id: uuid.UUID,
    *,
    type: NotificationType,
    message: str,
    link: str | None = None,
    related_player_id: uuid.UUID | None = None,
    related_club_id: uuid.UUID | None = None,
    **push_fields,
) -> None:
    """Create one notification per role-mapped club member (TRA-152).
    `push_fields` are create_notification's push and `once` arguments."""
    for user_id in await club_recipient_user_ids(db, club_id, type):
        await create_notification(
            db,
            recipient_user_id=user_id,
            type=type,
            message=message,
            link=link,
            related_player_id=related_player_id,
            related_club_id=related_club_id,
            **push_fields,
        )


async def club_member_user_ids(db: AsyncSession, club_id: uuid.UUID) -> list[uuid.UUID]:
    """Every member of a club (owner + all staff, any role) — for WS pushes,
    which are just 'refresh this view' signals, not role-scoped content."""
    from app.clubs.models import Club, ClubStaff

    club_id = uuid.UUID(str(club_id))
    club_result = await db.execute(select(Club).where(Club.id == club_id))
    club = club_result.scalar_one_or_none()
    if club is None:
        return []
    staff_result = await db.execute(
        select(ClubStaff.user_id).where(ClubStaff.club_id == club_id)
    )
    return [club.user_id] + [uuid.UUID(str(uid)) for uid in staff_result.scalars()]


# ── Domain-specific notification helpers ─────────────────────────────────────


async def notify_player_available(db: AsyncSession, player_id: uuid.UUID) -> None:
    """Fan out PLAYER_AVAILABLE to all clubs with the player shortlisted or
    interested — role-routed per club via notify_club (TRA-152)."""
    from app.players.models import Player
    from app.scouting.models import PlayerInterest, Shortlist, ShortlistItem

    # Coerce to UUID — SQLite may return strings from scalar subqueries
    if isinstance(player_id, str):
        player_id = uuid.UUID(player_id)

    player_result = await db.execute(select(Player).where(Player.id == player_id))
    player = player_result.scalar_one_or_none()
    if player is None:
        return

    # Load shortlists that contain this player, then extract club_ids in Python
    sl_result = await db.execute(
        select(Shortlist)
        .join(ShortlistItem, ShortlistItem.shortlist_id == Shortlist.id)
        .where(ShortlistItem.player_id == player_id)
        .distinct()
    )
    shortlist_club_ids = {sl.club_id for sl in sl_result.scalars()}

    # Load interests for this player
    interest_result = await db.execute(
        select(PlayerInterest).where(PlayerInterest.player_id == player_id)
    )
    interest_club_ids = {pi.club_id for pi in interest_result.scalars()}

    club_ids = shortlist_club_ids | interest_club_ids
    # Clubs his listing shuts out aren't told he's available.
    from app.clubs.models import Club
    from app.sales import service as sales_service

    sale = await sales_service.get_open_sale_for_player(db, player_id)
    if club_ids and sale is not None and (sale.excluded_club_ids or sale.excluded_leagues):
        clubs = (await db.execute(select(Club).where(Club.id.in_(club_ids)))).scalars()
        shut_out = {str(c.id) for c in clubs if sales_service.excludes(sale, c)}
        club_ids = {c for c in club_ids if str(c) not in shut_out}
    if not club_ids:
        return

    for club_id in club_ids:
        cid = club_id if isinstance(club_id, uuid.UUID) else uuid.UUID(str(club_id))
        pid = player_id if isinstance(player_id, uuid.UUID) else uuid.UUID(str(player_id))
        # TRA-152: market events reach scouts too (D5 role mapping).
        await notify_club(
            db,
            cid,
            type=NotificationType.PLAYER_AVAILABLE,
            message=f"{player.name} is now available",
            link=f"/players/market/{pid}",
            related_player_id=pid,
            related_club_id=cid,
        )


async def notify_upcoming_events(db: AsyncSession) -> None:
    """Background job: notify about offers expiring soon and instalments due."""
    now = datetime.now(timezone.utc)

    # Offers expiring within 24h
    await _notify_expiring_offers(db, now)

    # TRA-76: instalments due within 3 days (or overdue)
    await _notify_instalments_due(db, now)


async def _notify_instalments_due(db: AsyncSession, now: datetime) -> None:
    from app.deals.models import Deal, DealInstalment

    cutoff = (now + timedelta(days=3)).date()
    result = await db.execute(
        select(DealInstalment, Deal)
        .join(Deal, Deal.id == DealInstalment.deal_id)
        .where(DealInstalment.paid.is_(False), DealInstalment.due_date <= cutoff)
    )
    rows = list(result.all())
    if not rows:
        return

    for inst, deal in rows:
        overdue = inst.due_date < now.date()
        amount_str = f"£{inst.amount:,.0f}"
        # The job runs hourly: tell each person once when the instalment
        # falls due soon, and once more if it goes overdue.
        key = f"instalment:{inst.id}:{'overdue' if overdue else 'due'}"
        await notify_club(
            db,
            uuid.UUID(str(deal.buyer_club_id)),
            type=NotificationType.INSTALMENT_DUE,
            message=(
                f"Instalment of {amount_str} is {'overdue' if overdue else 'due soon'}"
            ),
            link=f"/deals/{deal.id}",
            related_player_id=deal.player_id,
            group_key=key,
            once=True,
        )
        if deal.seller_club_id:
            await notify_club(
                db,
                uuid.UUID(str(deal.seller_club_id)),
                type=NotificationType.INSTALMENT_DUE,
                message=(
                    f"You are owed an instalment of {amount_str}, "
                    f"{'now overdue' if overdue else 'due soon'}"
                ),
                link=f"/deals/{deal.id}",
                related_player_id=deal.player_id,
                group_key=key,
                once=True,
            )


async def _notify_expiring_offers(db: AsyncSession, now: datetime) -> None:
    from app.offers.models import Offer, OfferStatus

    cutoff = now + timedelta(hours=24)
    result = await db.execute(
        select(Offer).where(
            Offer.status.in_([OfferStatus.SENT, OfferStatus.COUNTERED]),
            Offer.expires_at != None,  # noqa: E711
            Offer.expires_at <= cutoff,
            Offer.expires_at > now,
        )
    )
    offers = list(result.scalars())
    if not offers:
        return

    for offer in offers:
        if offer.from_club_id:
            await notify_club(
                db,
                uuid.UUID(str(offer.from_club_id)),
                type=NotificationType.OFFER_EXPIRING,
                message="Your offer is expiring soon",
                link=f"/offers/{offer.id}",
                related_player_id=offer.player_id,
                # The job runs hourly with a 24-hour window: once per offer.
                group_key=f"offer:{offer.id}",
                deadline_at=offer.expires_at,
                once=True,
            )


# ── Notification preferences ──────────────────────────────────────────────────


async def get_preference_map(db: AsyncSession, user_id: uuid.UUID) -> dict[NotificationType, NotificationPreference]:
    """Return existing preference override rows keyed by type."""
    result = await db.execute(
        select(NotificationPreference).where(NotificationPreference.user_id == user_id)
    )
    return {p.type: p for p in result.scalars()}


async def get_disabled_types(db: AsyncSession, user_id: uuid.UUID) -> set[NotificationType]:
    """Return the set of notification types the user has disabled (in-app)."""
    prefs = await get_preference_map(db, user_id)
    return {t for t, p in prefs.items() if not p.enabled}


async def get_email_disabled_types(db: AsyncSession, user_id: uuid.UUID) -> set[NotificationType]:
    """Return the set of notification types the user has disabled email delivery for."""
    prefs = await get_preference_map(db, user_id)
    return {t for t, p in prefs.items() if not p.email_enabled}


async def _get_or_create_preference(
    db: AsyncSession, user_id: uuid.UUID, type: NotificationType
) -> NotificationPreference:
    result = await db.execute(
        select(NotificationPreference).where(
            NotificationPreference.user_id == user_id,
            NotificationPreference.type == type,
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        row = NotificationPreference(user_id=user_id, type=type)
        db.add(row)
        await db.flush()
    return row


async def set_preference(
    db: AsyncSession, user_id: uuid.UUID, type: NotificationType, enabled: bool
) -> None:
    """Enable or disable in-app delivery of a notification type for a user."""
    row = await _get_or_create_preference(db, user_id, type)
    row.enabled = enabled
    await db.flush()


async def get_push_disabled_types(db: AsyncSession, user_id: uuid.UUID) -> set[NotificationType]:
    """Return the set of notification types the user has switched phone pushes off for."""
    prefs = await get_preference_map(db, user_id)
    return {t for t, p in prefs.items() if not p.push_enabled}


async def set_push_preference(
    db: AsyncSession, user_id: uuid.UUID, type: NotificationType, push_enabled: bool
) -> None:
    """Switch phone pushes for a notification type on or off for a user."""
    row = await _get_or_create_preference(db, user_id, type)
    row.push_enabled = push_enabled
    await db.flush()


async def set_email_preference(
    db: AsyncSession, user_id: uuid.UUID, type: NotificationType, email_enabled: bool
) -> None:
    """Enable or disable email delivery of a notification type for a user."""
    row = await _get_or_create_preference(db, user_id, type)
    row.email_enabled = email_enabled
    await db.flush()


async def with_subjects(db: AsyncSession, notifications) -> list:
    """Notifications as responses, each with the player and club it is about
    (name and picture), loaded in one query each for the page."""
    from app.clubs.models import Club
    from app.notifications.schemas import NotificationResponse, NotificationSubject
    from app.players.models import Player

    player_ids = {n.related_player_id for n in notifications if n.related_player_id}
    club_ids = {n.related_club_id for n in notifications if n.related_club_id}
    players = {r.id: r for r in (await db.execute(
        select(Player.id, Player.name, Player.photo_url).where(Player.id.in_(player_ids)))).all()} if player_ids else {}
    clubs = {r.id: r for r in (await db.execute(
        select(Club.id, Club.name, Club.crest_url).where(Club.id.in_(club_ids)))).all()} if club_ids else {}
    # The push wording's deadlines, written in each recipient's timezone.
    from app.lite.models import UserPreference
    from app.notifications.copy import render
    from app.notifications.push import _zone
    from app.notifications.tiers import tier_of

    recipients = {n.recipient_user_id for n in notifications}
    zones = {r.user_id: _zone(r.timezone) for r in (await db.execute(
        select(UserPreference.user_id, UserPreference.timezone).where(UserPreference.user_id.in_(recipients))
    )).all()} if recipients else {}
    now = datetime.now(timezone.utc)

    out = []
    for n in notifications:
        resp = NotificationResponse.model_validate(n)
        zone = zones.get(n.recipient_user_id, _zone(None))
        resp.title = render(n.title, n.deadline_at, zone, now)
        resp.body = render(n.body, n.deadline_at, zone, now)
        resp.tier = tier_of(n.type).value
        if (p := players.get(n.related_player_id)) is not None:
            resp.player = NotificationSubject(id=p.id, name=p.name, image_url=p.photo_url)
        if (c := clubs.get(n.related_club_id)) is not None:
            resp.club = NotificationSubject(id=c.id, name=c.name, image_url=c.crest_url)
        out.append(resp)
    return out
