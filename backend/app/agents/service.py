import csv
import io
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.schemas import (
    MatchCandidate,
    RosterImportRequest,
    RosterImportResult,
    RosterPreviewResponse,
    RosterPreviewRow,
)
from app.auth.models import AgentProfile
from app.mandates.models import Mandate, MandateStatus
from app.players.models import Player, PlayerPosition


# ── Column name aliases ───────────────────────────────────────────────────────

_COLUMN_ALIASES: dict[str, list[str]] = {
    "name":            ["name", "player name", "full name", "player"],
    "dob":             ["dob", "date of birth", "birth date", "birthdate", "birthday"],
    "nationality":     ["nationality", "nation", "country", "citizenship"],
    "position":        ["position", "pos", "role"],
    "current_club":    ["current club", "club", "team", "current team"],
    "contract_expiry": [
        "contract expiry", "contract end", "expiry", "expiry date",
        "contract expires", "contract expiration",
    ],
}


def _normalize_row(raw: dict[str, str]) -> dict[str, str | None]:
    out: dict[str, str | None] = {}
    lowered = {k.strip().lower(): v.strip() or None for k, v in raw.items()}
    for field, aliases in _COLUMN_ALIASES.items():
        for alias in aliases:
            if alias in lowered:
                out[field] = lowered[alias]
                break
        else:
            out[field] = None
    return out


# ── Profile operations ────────────────────────────────────────────────────────

async def list_invitations(db: AsyncSession, agent_profile_id: uuid.UUID) -> list:
    from sqlalchemy.orm import selectinload
    from app.agents.models import AgentDealInvitation, InvitationStatus
    from app.deals.models import Deal

    result = await db.execute(
        select(AgentDealInvitation)
        .where(
            AgentDealInvitation.agent_id == agent_profile_id,
            AgentDealInvitation.status == InvitationStatus.PENDING,
        )
        .options(
            selectinload(AgentDealInvitation.deal).selectinload(Deal.buyer_club),
            selectinload(AgentDealInvitation.deal).selectinload(Deal.seller_club),
            selectinload(AgentDealInvitation.deal).selectinload(Deal.player),
        )
        .order_by(AgentDealInvitation.created_at.desc())
    )
    return list(result.scalars())


async def update_profile(db: AsyncSession, profile: AgentProfile, **kwargs) -> AgentProfile:
    for k, v in kwargs.items():
        setattr(profile, k, v)
    await db.flush()
    return profile


async def list_represented_players(
    db: AsyncSession, agent_profile_id: uuid.UUID
) -> list[tuple[Mandate, Player]]:
    result = await db.execute(
        select(Mandate, Player)
        .join(Player, Player.id == Mandate.player_id)
        .where(
            Mandate.agent_id == agent_profile_id,
            Mandate.status == MandateStatus.ACTIVE,
        )
        .order_by(Player.name)
    )
    return result.all()


# ── Roster import ─────────────────────────────────────────────────────────────

async def parse_csv_roster(
    db: AsyncSession,
    content: bytes,
) -> RosterPreviewResponse:
    text = content.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    rows: list[RosterPreviewRow] = []

    for i, raw_row in enumerate(reader):
        norm = _normalize_row(raw_row)
        name = norm.get("name")
        if not name:
            continue

        result = await db.execute(
            select(Player).where(Player.name.ilike(name))
        )
        matches = result.scalars().all()

        if len(matches) == 0:
            match_status = "no_match"
        elif len(matches) == 1:
            match_status = "matched"
        else:
            match_status = "ambiguous"

        candidates = [
            MatchCandidate(
                player_id=str(m.id),
                player_name=m.name,
                player_position=str(m.position) if m.position else None,
                player_club=m.team_name,
            )
            for m in matches[:5]
        ]

        rows.append(
            RosterPreviewRow(
                row_index=i,
                name=name,
                dob=norm.get("dob"),
                nationality=norm.get("nationality"),
                position=norm.get("position"),
                current_club=norm.get("current_club"),
                contract_expiry=norm.get("contract_expiry"),
                match_status=match_status,
                match_candidates=candidates,
            )
        )

    return RosterPreviewResponse(rows=rows)


_POSITION_MAP: dict[str, PlayerPosition] = {
    # Goalkeeper
    "GK": PlayerPosition.GK, "GOALKEEPER": PlayerPosition.GK, "KEEPER": PlayerPosition.GK,
    # Defence
    "DEF": PlayerPosition.DEF, "DEFENDER": PlayerPosition.DEF, "DEFENCE": PlayerPosition.DEF,
    "DEFENSE": PlayerPosition.DEF, "CB": PlayerPosition.DEF, "LB": PlayerPosition.DEF,
    "RB": PlayerPosition.DEF, "LWB": PlayerPosition.DEF, "RWB": PlayerPosition.DEF,
    "FULLBACK": PlayerPosition.DEF, "FULL-BACK": PlayerPosition.DEF,
    "CENTRE-BACK": PlayerPosition.DEF, "CENTER-BACK": PlayerPosition.DEF,
    "WING-BACK": PlayerPosition.DEF,
    # Midfield
    "MID": PlayerPosition.MID, "MIDFIELD": PlayerPosition.MID, "MIDFIELDER": PlayerPosition.MID,
    "CM": PlayerPosition.MID, "CDM": PlayerPosition.MID, "CAM": PlayerPosition.MID,
    "DM": PlayerPosition.MID, "AM": PlayerPosition.MID, "LM": PlayerPosition.MID,
    "RM": PlayerPosition.MID, "WINGER": PlayerPosition.MID, "WING": PlayerPosition.MID,
    # Forward
    "FWD": PlayerPosition.FWD, "FORWARD": PlayerPosition.FWD, "STRIKER": PlayerPosition.FWD,
    "ATTACKER": PlayerPosition.FWD, "CF": PlayerPosition.FWD, "ST": PlayerPosition.FWD,
    "LW": PlayerPosition.FWD, "RW": PlayerPosition.FWD,
}


def _parse_position(raw: str | None) -> PlayerPosition | None:
    if not raw:
        return None
    return _POSITION_MAP.get(raw.strip().upper())


async def import_roster(
    db: AsyncSession,
    agent_profile_id: uuid.UUID,
    request: RosterImportRequest,
) -> RosterImportResult:
    from app.mandates.service import create_mandate

    created = 0
    linked = 0
    skipped = 0
    errors: list[str] = []
    mandate_ids: list[str] = []

    for row in request.rows:
        if row.action == "skip":
            skipped += 1
            continue

        label = row.name or (row.player_id or "row")

        if row.action == "link":
            if not row.player_id:
                errors.append(f"{label}: link action requires player_id")
                continue
            try:
                player_id = uuid.UUID(row.player_id)
            except ValueError:
                errors.append(f"{label}: invalid player_id")
                continue

        else:  # create
            if not row.name:
                errors.append("create action requires name")
                continue
            player = Player(
                name=row.name,
                birth_date=row.dob,
                nationality=row.nationality,
                position=_parse_position(row.position),
                team_name=row.current_club,
            )
            db.add(player)
            await db.flush()
            player_id = player.id
            created += 1

        try:
            mandate = await create_mandate(
                db,
                agent_profile_id=agent_profile_id,
                player_id=player_id,
                exclusive=request.exclusive,
                start_date=request.start_date,
                end_date=request.end_date,
                territory=request.territory,
            )
            mandate_ids.append(str(mandate.id))
            if row.action == "link":
                linked += 1
        except ValueError as exc:
            errors.append(f"{label}: {exc}")

    return RosterImportResult(
        created=created,
        linked=linked,
        skipped=skipped,
        errors=errors,
        mandate_ids=mandate_ids,
    )
