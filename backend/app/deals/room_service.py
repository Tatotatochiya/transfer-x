"""TRA-81 — deal room service: versioned terms, threaded comments, attachments."""

import re
import uuid
from decimal import Decimal
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User, UserType
from app.deals.models import Deal
from app.deals.room_models import DealAttachment, DealComment, DealTermsVersion

_TERMS_FIELDS = [
    "agreed_fee", "agreed_wage_weekly", "deal_type",
    "loan_start", "loan_end", "loan_fee", "option_to_buy",
    "obligation_to_buy", "obligation_conditions", "sell_on_pct",
]

_UPLOAD_ROOT = Path(__file__).resolve().parent.parent.parent / "uploads" / "deal_attachments"
_MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024  # 10MB
_ALLOWED_EXTENSIONS = {".pdf", ".doc", ".docx", ".jpg", ".jpeg", ".png"}
_SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


def _serialize_value(value):
    if isinstance(value, Decimal):
        return str(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if hasattr(value, "value"):  # enum
        return value.value
    return value


def serialize_deal_terms(deal: Deal) -> dict:
    return {field: _serialize_value(getattr(deal, field)) for field in _TERMS_FIELDS}


# ── Authorization ─────────────────────────────────────────────────────────────


async def is_deal_participant(db: AsyncSession, deal: Deal, current_user: User) -> bool:
    if current_user.is_superuser:
        return True

    if current_user.user_type == UserType.CLUB:
        from app.clubs import service as clubs_service
        # TRA-146: owner-or-staff — staff of the buyer/seller club are deal
        # participants too. Writes stay gated by DEAL_WRITE (TRA-151/D4), so
        # this visibility widening grants no write access to SCOUT/READONLY.
        club = await clubs_service.get_club_for_user(db, current_user.id)
        parties = {deal.buyer_club_id}
        if deal.seller_club_id:
            parties.add(deal.seller_club_id)
        return club is not None and club.id in parties

    if current_user.user_type == UserType.AGENT:
        from app.agents.models import AgentDealInvitation, AgentNegotiation, InvitationStatus
        from app.auth.models import AgentProfile
        result = await db.execute(select(AgentProfile).where(AgentProfile.user_id == current_user.id))
        profile = result.scalar_one_or_none()
        if profile is None:
            return False
        neg_result = await db.execute(
            select(AgentNegotiation).where(
                AgentNegotiation.deal_id == deal.id, AgentNegotiation.agent_id == profile.id
            )
        )
        if neg_result.scalar_one_or_none() is not None:
            return True
        # An invited agent must be able to view the deal room before their first
        # negotiation-terms write creates the AgentNegotiation row above —
        # otherwise they can never reach the UI that makes that write.
        inv_result = await db.execute(
            select(AgentDealInvitation).where(
                AgentDealInvitation.deal_id == deal.id,
                AgentDealInvitation.agent_id == profile.id,
                AgentDealInvitation.status != InvitationStatus.DECLINED,
            )
        )
        return inv_result.scalar_one_or_none() is not None

    if current_user.user_type == UserType.PLAYER:
        from app.auth.models import PlayerProfile
        result = await db.execute(select(PlayerProfile).where(PlayerProfile.user_id == current_user.id))
        pp = result.scalar_one_or_none()
        return pp is not None and pp.player_id == deal.player_id

    return False


async def get_deal_participants(db: AsyncSession, deal: Deal) -> list[dict]:
    """Resolve the deal's participant directory — for the @mention picker."""
    participants: list[dict] = []

    from app.clubs import service as clubs_service
    buyer = await clubs_service.get_club_by_id(db, deal.buyer_club_id)
    if buyer:
        participants.append({"user_id": buyer.user_id, "label": f"{buyer.name} (buyer)"})
    if deal.seller_club_id:
        seller = await clubs_service.get_club_by_id(db, deal.seller_club_id)
        if seller:
            participants.append({"user_id": seller.user_id, "label": f"{seller.name} (seller)"})

    from app.agents.models import AgentNegotiation
    from app.auth.models import AgentProfile
    neg_result = await db.execute(select(AgentNegotiation).where(AgentNegotiation.deal_id == deal.id))
    neg = neg_result.scalar_one_or_none()
    if neg is not None:
        agent_result = await db.execute(select(AgentProfile).where(AgentProfile.id == neg.agent_id))
        agent = agent_result.scalar_one_or_none()
        if agent:
            participants.append({"user_id": agent.user_id, "label": f"{agent.display_name} (agent)"})

    from app.auth.models import PlayerProfile
    pp_result = await db.execute(select(PlayerProfile).where(PlayerProfile.player_id == deal.player_id))
    pp = pp_result.scalar_one_or_none()
    if pp is not None:
        participants.append({"user_id": pp.user_id, "label": "Player"})

    return participants


async def label_for_user(db: AsyncSession, user_id: uuid.UUID | None) -> str | None:
    if user_id is None:
        return None
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        return None
    if user.user_type == UserType.CLUB:
        from app.clubs import service as clubs_service
        # Owner-or-staff: a staff member speaks for the club, so their
        # comments/audit rows are labeled with the club's name (TRA-146).
        club = await clubs_service.get_club_for_user(db, user.id)
        return club.name if club else "Club"
    if user.user_type == UserType.AGENT:
        from app.auth.models import AgentProfile
        result = await db.execute(select(AgentProfile).where(AgentProfile.user_id == user.id))
        agent = result.scalar_one_or_none()
        return agent.display_name if agent else "Agent"
    if user.user_type == UserType.PLAYER:
        return "Player"
    return "Staff"


# ── Versioned terms ────────────────────────────────────────────────────────────


async def create_terms_version(
    db: AsyncSession, deal: Deal, *, changed_by_user_id: uuid.UUID | None
) -> DealTermsVersion:
    last_result = await db.execute(
        select(func.max(DealTermsVersion.version_number)).where(DealTermsVersion.deal_id == deal.id)
    )
    last_version = last_result.scalar_one_or_none() or 0

    version = DealTermsVersion(
        deal_id=deal.id,
        version_number=last_version + 1,
        terms_snapshot=serialize_deal_terms(deal),
        changed_by_user_id=changed_by_user_id,
    )
    db.add(version)
    await db.flush()
    return version


async def list_terms_versions(db: AsyncSession, deal_id: uuid.UUID) -> list[DealTermsVersion]:
    result = await db.execute(
        select(DealTermsVersion)
        .where(DealTermsVersion.deal_id == deal_id)
        .order_by(DealTermsVersion.version_number.asc())
    )
    return list(result.scalars())


async def diff_versions(
    db: AsyncSession, deal_id: uuid.UUID, from_version: int | None, to_version: int | None
) -> tuple[int | None, int | None, list[dict]]:
    versions = await list_terms_versions(db, deal_id)
    if not versions:
        return None, None, []

    by_number = {v.version_number: v for v in versions}
    to_v = by_number.get(to_version) if to_version is not None else versions[-1]
    if to_v is None:
        return None, None, []

    if from_version is not None:
        from_v = by_number.get(from_version)
    else:
        idx = versions.index(to_v)
        from_v = versions[idx - 1] if idx > 0 else None

    from_snapshot = from_v.terms_snapshot if from_v else {f: None for f in _TERMS_FIELDS}
    to_snapshot = to_v.terms_snapshot

    changes = [
        {"field": field, "old_value": from_snapshot.get(field), "new_value": to_snapshot.get(field)}
        for field in _TERMS_FIELDS
        if from_snapshot.get(field) != to_snapshot.get(field)
    ]
    return (from_v.version_number if from_v else None), to_v.version_number, changes


# ── Comments ───────────────────────────────────────────────────────────────────


async def create_comment(
    db: AsyncSession,
    deal_id: uuid.UUID,
    *,
    author_user_id: uuid.UUID,
    body: str,
    parent_id: uuid.UUID | None,
    mentioned_user_ids: list[uuid.UUID],
) -> DealComment:
    comment = DealComment(
        deal_id=deal_id,
        parent_id=parent_id,
        author_user_id=author_user_id,
        body=body,
        mentioned_user_ids=[str(u) for u in mentioned_user_ids],
    )
    db.add(comment)
    await db.flush()
    return comment


async def list_comments(db: AsyncSession, deal_id: uuid.UUID) -> list[DealComment]:
    result = await db.execute(
        select(DealComment)
        .where(DealComment.deal_id == deal_id)
        .order_by(DealComment.created_at.asc())
    )
    return list(result.scalars())


async def get_comment(db: AsyncSession, comment_id: uuid.UUID) -> DealComment | None:
    result = await db.execute(select(DealComment).where(DealComment.id == comment_id))
    return result.scalar_one_or_none()


# ── Attachments ────────────────────────────────────────────────────────────────


class AttachmentValidationError(ValueError):
    pass


def validate_attachment(filename: str, size_bytes: int) -> str:
    """Returns a sanitized filename or raises AttachmentValidationError."""
    if size_bytes > _MAX_ATTACHMENT_BYTES:
        raise AttachmentValidationError("File exceeds the 10MB limit")
    ext = Path(filename).suffix.lower()
    if ext not in _ALLOWED_EXTENSIONS:
        raise AttachmentValidationError(
            f"File type {ext or '(none)'} not allowed. Allowed: {', '.join(sorted(_ALLOWED_EXTENSIONS))}"
        )
    safe_name = _SAFE_FILENAME_RE.sub("_", Path(filename).name)
    return safe_name or "attachment"


def save_attachment_bytes(deal_id: uuid.UUID, safe_filename: str, content: bytes) -> str:
    """Writes to disk and returns the storage path (relative to the uploads root)."""
    deal_dir = _UPLOAD_ROOT / str(deal_id)
    deal_dir.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid.uuid4()}_{safe_filename}"
    (deal_dir / stored_name).write_bytes(content)
    return f"{deal_id}/{stored_name}"


def read_attachment_bytes(storage_path: str) -> bytes:
    return (_UPLOAD_ROOT / storage_path).read_bytes()


async def create_attachment(
    db: AsyncSession,
    deal_id: uuid.UUID,
    *,
    uploaded_by_user_id: uuid.UUID,
    filename: str,
    content_type: str,
    size_bytes: int,
    storage_path: str,
) -> DealAttachment:
    attachment = DealAttachment(
        deal_id=deal_id,
        uploaded_by_user_id=uploaded_by_user_id,
        filename=filename,
        content_type=content_type,
        size_bytes=size_bytes,
        storage_path=storage_path,
    )
    db.add(attachment)
    await db.flush()
    return attachment


async def list_attachments(db: AsyncSession, deal_id: uuid.UUID) -> list[DealAttachment]:
    result = await db.execute(
        select(DealAttachment)
        .where(DealAttachment.deal_id == deal_id)
        .order_by(DealAttachment.created_at.asc())
    )
    return list(result.scalars())


async def get_attachment(db: AsyncSession, deal_id: uuid.UUID, attachment_id: uuid.UUID) -> DealAttachment | None:
    result = await db.execute(
        select(DealAttachment).where(DealAttachment.id == attachment_id, DealAttachment.deal_id == deal_id)
    )
    return result.scalar_one_or_none()
