"""M5 — Notification service layer."""

import asyncio
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

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
) -> Notification | None:
    pref = await db.execute(
        select(NotificationPreference).where(
            NotificationPreference.user_id == recipient_user_id,
            NotificationPreference.type == type,
        )
    )
    pref_row = pref.scalar_one_or_none()
    if pref_row is not None and not pref_row.enabled:
        return None  # Suppressed by user preference

    n = Notification(
        recipient_user_id=recipient_user_id,
        type=type,
        message=message,
        link=link,
        is_read=False,
        related_player_id=related_player_id,
        related_club_id=related_club_id,
    )
    db.add(n)
    await db.flush()

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
        from app.notifications.email import maybe_send_notification_email
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


async def list_notifications(
    db: AsyncSession,
    user_id: uuid.UUID,
    page: int = 1,
    page_size: int = 30,
) -> tuple[list[Notification], int]:
    q = select(Notification).where(Notification.recipient_user_id == user_id)
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


async def mark_all_read(db: AsyncSession, user_id: uuid.UUID) -> int:
    result = await db.execute(
        update(Notification)
        .where(Notification.recipient_user_id == user_id, Notification.is_read == False)  # noqa: E712
        .values(is_read=True)
    )
    return result.rowcount


# ── Domain-specific notification helpers ─────────────────────────────────────


async def notify_player_available(db: AsyncSession, player_id: uuid.UUID) -> None:
    """Fan out PLAYER_AVAILABLE notifications to all clubs with the player shortlisted or interested.

    Fetches the club's owner user_id to address the notification.
    """
    from app.clubs.models import Club
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
    if not club_ids:
        return

    # Get owner user_ids for those clubs
    clubs_result = await db.execute(
        select(Club).where(Club.id.in_([c if isinstance(c, uuid.UUID) else uuid.UUID(str(c)) for c in club_ids]))
    )
    clubs = list(clubs_result.scalars())

    for club in clubs:
        pid = player_id if isinstance(player_id, uuid.UUID) else uuid.UUID(str(player_id))
        await create_notification(
            db,
            recipient_user_id=club.user_id,
            type=NotificationType.PLAYER_AVAILABLE,
            message=f"{player.name} is now available",
            link=f"/players/market/{pid}",
            related_player_id=pid,
            related_club_id=club.id,
        )


async def notify_upcoming_events(db: AsyncSession) -> None:
    """Background job: notify about offers expiring soon and auctions ending soon."""
    now = datetime.now(timezone.utc)

    # Offers expiring within 24h
    await _notify_expiring_offers(db, now)

    # Auctions ending within 1h
    await _notify_ending_auctions(db, now)

    # TRA-76: instalments due within 3 days (or overdue)
    await _notify_instalments_due(db, now)


async def _notify_instalments_due(db: AsyncSession, now: datetime) -> None:
    from app.clubs.models import Club
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

    club_ids = {uuid.UUID(str(d.buyer_club_id)) for _, d in rows} | {
        uuid.UUID(str(d.seller_club_id)) for _, d in rows if d.seller_club_id
    }
    clubs_result = await db.execute(select(Club).where(Club.id.in_(club_ids)))
    clubs_by_id = {c.id: c for c in clubs_result.scalars()}

    for inst, deal in rows:
        overdue = inst.due_date < now.date()
        amount_str = f"£{inst.amount:,.0f}"
        buyer = clubs_by_id.get(uuid.UUID(str(deal.buyer_club_id)))
        if buyer:
            await create_notification(
                db,
                recipient_user_id=buyer.user_id,
                type=NotificationType.INSTALMENT_DUE,
                message=(
                    f"Instalment of {amount_str} is {'overdue' if overdue else 'due soon'}"
                ),
                link=f"/deals/{deal.id}",
                related_player_id=deal.player_id,
            )
        seller = clubs_by_id.get(uuid.UUID(str(deal.seller_club_id))) if deal.seller_club_id else None
        if seller:
            await create_notification(
                db,
                recipient_user_id=seller.user_id,
                type=NotificationType.INSTALMENT_DUE,
                message=(
                    f"You are owed an instalment of {amount_str}, "
                    f"{'now overdue' if overdue else 'due soon'}"
                ),
                link=f"/deals/{deal.id}",
                related_player_id=deal.player_id,
            )


async def _notify_expiring_offers(db: AsyncSession, now: datetime) -> None:
    from app.offers.models import Offer, OfferStatus
    from app.clubs.models import Club

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

    # Batch-load all clubs needed in one query
    club_ids = list({uuid.UUID(str(o.from_club_id)) for o in offers if o.from_club_id})
    clubs_result = await db.execute(select(Club).where(Club.id.in_(club_ids)))
    clubs_by_id = {c.id: c for c in clubs_result.scalars()}

    for offer in offers:
        from_club = clubs_by_id.get(uuid.UUID(str(offer.from_club_id))) if offer.from_club_id else None
        if from_club:
            await create_notification(
                db,
                recipient_user_id=from_club.user_id,
                type=NotificationType.OFFER_EXPIRING,
                message="Your offer is expiring soon",
                link=f"/offers/{offer.id}",
                related_player_id=offer.player_id,
            )


async def _notify_ending_auctions(db: AsyncSession, now: datetime) -> None:
    from app.clubs.models import Club
    from app.sales.models import Bid, BidStatus, Sale, SaleStatus, SaleType

    cutoff = now + timedelta(hours=1)
    result = await db.execute(
        select(Sale).where(
            Sale.status == SaleStatus.OPEN,
            Sale.sale_type == SaleType.AUCTION,
            Sale.deadline != None,  # noqa: E711
            Sale.deadline <= cutoff,
            Sale.deadline > now,
        )
    )
    sales = list(result.scalars())
    if not sales:
        return

    sale_ids = [s.id for s in sales]

    # Batch-load all active bids for these sales in one query
    bids_result = await db.execute(
        select(Bid).where(Bid.sale_id.in_(sale_ids), Bid.status == BidStatus.ACTIVE)
    )
    all_bids = list(bids_result.scalars())
    bids_by_sale: dict[uuid.UUID, list[Bid]] = {}
    for bid in all_bids:
        bids_by_sale.setdefault(uuid.UUID(str(bid.sale_id)), []).append(bid)

    # Batch-load all clubs (sellers + buyers) in one query
    club_ids = list(
        {uuid.UUID(str(s.seller_club_id)) for s in sales if s.seller_club_id}
        | {uuid.UUID(str(b.buyer_club_id)) for b in all_bids if b.buyer_club_id}
    )
    clubs_result = await db.execute(select(Club).where(Club.id.in_(club_ids)))
    clubs_by_id = {c.id: c for c in clubs_result.scalars()}

    for sale in sales:
        # Notify seller
        seller = clubs_by_id.get(uuid.UUID(str(sale.seller_club_id))) if sale.seller_club_id else None
        if seller:
            await create_notification(
                db,
                recipient_user_id=seller.user_id,
                type=NotificationType.AUCTION_ENDING,
                message="Auction ending soon",
                link=f"/sales/{sale.id}",
                related_player_id=sale.player_id,
            )

        # Notify all active bidders
        for bid in bids_by_sale.get(uuid.UUID(str(sale.id)), []):
            buyer = clubs_by_id.get(uuid.UUID(str(bid.buyer_club_id))) if bid.buyer_club_id else None
            if buyer:
                await create_notification(
                    db,
                    recipient_user_id=buyer.user_id,
                    type=NotificationType.AUCTION_ENDING,
                    message="Auction you're bidding on is ending soon",
                    link=f"/sales/{sale.id}",
                    related_player_id=sale.player_id,
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


async def set_email_preference(
    db: AsyncSession, user_id: uuid.UUID, type: NotificationType, email_enabled: bool
) -> None:
    """Enable or disable email delivery of a notification type for a user."""
    row = await _get_or_create_preference(db, user_id, type)
    row.email_enabled = email_enabled
    await db.flush()
