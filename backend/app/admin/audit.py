"""The admin audit trail: every change TransferX staff make in the admin
panel, who made it, when, and why.

Each event is an ordinary AuditEvent with an `admin.` action, so it sits in
the same log as the deal and offer history, and the Audit log page and its
Excel export read them all. `reason` is required for anything destructive
(deleting, deactivating, granting or removing staff rights, cancelling,
withdrawing, changing a budget); the endpoints enforce that.
"""
import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import service as audit_service

ADMIN_PREFIX = "admin."


def _plain(value: Any) -> Any:
    """JSON-safe: Decimals, UUIDs, dates and enums as text."""
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_plain(v) for v in value]
    if isinstance(value, (Decimal, uuid.UUID)):
        return str(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if hasattr(value, "value") and not isinstance(value, (str, int, float, bool)):
        return value.value
    return value


def changes(before: dict, after: dict) -> dict:
    """Only the fields that changed, as {field: [old, new]}."""
    return {k: [_plain(before.get(k)), _plain(v)] for k, v in after.items() if _plain(before.get(k)) != _plain(v)}


async def record(
    db: AsyncSession,
    admin,
    action: str,
    *,
    entity_type: str,
    entity_id: uuid.UUID,
    description: str,
    reason: str | None = None,
    details: dict | None = None,
) -> None:
    """Write one admin audit event. Call before the commit, in the same
    transaction as the change, so the two stand or fall together."""
    payload: dict = {"admin_action": True}
    if reason:
        payload["reason"] = reason
    if details:
        payload.update(_plain(details))
    await audit_service.emit(
        db,
        entity_type=entity_type,
        entity_id=uuid.UUID(str(entity_id)),
        action=ADMIN_PREFIX + action,
        actor_user_id=admin.id,
        payload=payload,
        description=description,
    )
