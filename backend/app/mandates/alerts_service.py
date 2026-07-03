"""TRA-134 — client-roster alert generation (contract expiry, valuation change, club interest)."""

import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.mandates.models import AlertSeverity, AlertType, ClientAlert, Mandate, MandateStatus

_DEDUP_WINDOW_DAYS = 30


# ── Reads ─────────────────────────────────────────────────────────────────────


async def list_alerts_for_agent(db: AsyncSession, agent_id: uuid.UUID, limit: int = 100) -> list[ClientAlert]:
    result = await db.execute(
        select(ClientAlert)
        .where(ClientAlert.agent_id == agent_id)
        .order_by(ClientAlert.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars())


async def list_alerts_for_mandate(db: AsyncSession, mandate_id: uuid.UUID) -> list[ClientAlert]:
    result = await db.execute(
        select(ClientAlert).where(ClientAlert.mandate_id == mandate_id).order_by(ClientAlert.created_at.desc())
    )
    return list(result.scalars())


async def mark_alert_read(db: AsyncSession, alert_id: uuid.UUID, agent_id: uuid.UUID) -> ClientAlert | None:
    result = await db.execute(select(ClientAlert).where(ClientAlert.id == alert_id, ClientAlert.agent_id == agent_id))
    alert = result.scalar_one_or_none()
    if alert is not None:
        alert.is_read = True
        await db.flush()
    return alert


# ── Alert creation ────────────────────────────────────────────────────────────


async def _create_alert(
    db: AsyncSession, mandate: Mandate, *, alert_type: AlertType, severity: AlertSeverity, message: str, context: dict
) -> ClientAlert:
    alert = ClientAlert(
        mandate_id=mandate.id,
        agent_id=mandate.agent_id,
        player_id=mandate.player_id,
        alert_type=alert_type,
        severity=severity,
        message=message,
        context=context,
    )
    db.add(alert)
    await db.flush()

    from app.auth.models import AgentProfile
    from app.notifications import service as notif_service
    from app.notifications.models import NotificationType

    agent_result = await db.execute(select(AgentProfile).where(AgentProfile.id == mandate.agent_id))
    agent = agent_result.scalar_one_or_none()
    if agent is not None:
        await notif_service.create_notification(
            db,
            recipient_user_id=agent.user_id,
            type=NotificationType.CLIENT_ALERT,
            message=message,
            link=f"/agent/clients/{mandate.id}",
            related_player_id=mandate.player_id,
        )
    return alert


async def _has_recent_alert(db: AsyncSession, mandate_id: uuid.UUID, alert_type: AlertType, since: datetime) -> bool:
    result = await db.execute(
        select(ClientAlert.id)
        .where(
            ClientAlert.mandate_id == mandate_id,
            ClientAlert.alert_type == alert_type,
            ClientAlert.created_at >= since,
        )
        .limit(1)
    )
    return result.scalar_one_or_none() is not None


async def _check_contract_expiry(db: AsyncSession, mandate: Mandate, player) -> bool:
    if not mandate.alert_contract_expiry_enabled or player.contract_expiry is None:
        return False

    days_remaining = (player.contract_expiry - date.today()).days
    if days_remaining < 0:
        return False  # already expired — not a "leverage window" alert
    months_remaining = days_remaining / 30.44
    if months_remaining > mandate.alert_contract_expiry_months:
        return False

    since = datetime.now(timezone.utc) - timedelta(days=_DEDUP_WINDOW_DAYS)
    if await _has_recent_alert(db, mandate.id, AlertType.CONTRACT_EXPIRY, since):
        return False

    severity = AlertSeverity.RED if months_remaining < 6 else AlertSeverity.AMBER
    months_display = max(1, round(months_remaining))
    await _create_alert(
        db, mandate,
        alert_type=AlertType.CONTRACT_EXPIRY,
        severity=severity,
        message=f"{player.name}'s contract expires in {months_display} month{'s' if months_display != 1 else ''} — leverage window open",
        context={"months_remaining": round(months_remaining, 1), "contract_expiry": player.contract_expiry.isoformat()},
    )
    return True


async def _check_valuation_change(db: AsyncSession, mandate: Mandate, player) -> bool:
    if not mandate.alert_valuation_change_enabled or player.market_value is None:
        return False

    if mandate.last_seen_market_value is None:
        # First time we've seen a valuation for this client — set the baseline, no alert yet.
        mandate.last_seen_market_value = player.market_value
        await db.flush()
        return False

    baseline = mandate.last_seen_market_value
    if baseline == 0:
        return False

    pct_change = (player.market_value - baseline) / baseline
    threshold = mandate.alert_valuation_change_pct
    if abs(pct_change) < threshold:
        return False

    if pct_change <= -2 * threshold:
        severity = AlertSeverity.RED
    elif pct_change < 0:
        severity = AlertSeverity.AMBER
    else:
        severity = AlertSeverity.GREEN

    direction = "risen" if pct_change > 0 else "dropped"
    await _create_alert(
        db, mandate,
        alert_type=AlertType.VALUATION_CHANGE,
        severity=severity,
        message=f"{player.name}'s valuation has {direction} {abs(pct_change) * 100:.0f}% since last check",
        context={
            "previous_value": str(baseline),
            "current_value": str(player.market_value),
            "pct_change": round(float(pct_change) * 100, 1),
        },
    )
    mandate.last_seen_market_value = player.market_value
    await db.flush()
    return True


async def _check_club_interest(db: AsyncSession, mandate: Mandate, player) -> int:
    if not mandate.alert_club_interest_enabled:
        return 0

    from app.clubs.models import Club
    from app.scouting.models import PlayerInterest, Shortlist, ShortlistItem

    interest_result = await db.execute(select(PlayerInterest.club_id).where(PlayerInterest.player_id == player.id))
    interested_club_ids = {row[0] for row in interest_result.all()}

    shortlist_result = await db.execute(
        select(Shortlist.club_id)
        .join(ShortlistItem, ShortlistItem.shortlist_id == Shortlist.id)
        .where(ShortlistItem.player_id == player.id)
    )
    interested_club_ids |= {row[0] for row in shortlist_result.all()}

    already_seen = {uuid.UUID(str(cid)) for cid in mandate.last_seen_interest_club_ids}
    all_seen_ids = {uuid.UUID(str(cid)) for cid in interested_club_ids}
    new_club_ids = all_seen_ids - already_seen
    if not new_club_ids:
        return 0

    clubs_result = await db.execute(select(Club).where(Club.id.in_(new_club_ids)))
    clubs = list(clubs_result.scalars())

    for club in clubs:
        await _create_alert(
            db, mandate,
            alert_type=AlertType.CLUB_INTEREST,
            severity=AlertSeverity.GREEN,
            message=f"{club.name} has shown interest in {player.name}",
            context={"club_id": str(club.id), "club_name": club.name},
        )

    mandate.last_seen_interest_club_ids = [str(cid) for cid in (already_seen | new_club_ids)]
    await db.flush()
    return len(clubs)


async def check_and_create_alerts(db: AsyncSession) -> int:
    """Background job entrypoint — scans all active mandates, returns count of alerts created."""
    from app.players.models import Player

    result = await db.execute(
        select(Mandate, Player).join(Player, Player.id == Mandate.player_id).where(Mandate.status == MandateStatus.ACTIVE)
    )
    rows = result.all()

    total = 0
    for mandate, player in rows:
        if await _check_contract_expiry(db, mandate, player):
            total += 1
        if await _check_valuation_change(db, mandate, player):
            total += 1
        total += await _check_club_interest(db, mandate, player)
    return total
