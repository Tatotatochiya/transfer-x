"""Where API-Football says a player is, against his TransferX registration.

On TransferX a player's club changes only through a deal. Real football
moves on regardless: a player can join another club or go out on loan while
his (demo) contract still has him where he was. This module notices that,
and lets TransferX staff act on it: `apply_move` corrects the registration
(audited, with a reason), `dismiss_move` leaves it as it is and stops
reporting that move. Neither moves any money; a correction isn't a transfer.

Two kinds of evidence, both from stored API-Football data:
- **his latest transfer** (player_transfers), if it happened this season and
  after his TransferX contract started;
- **who he has played for this season** (club rows in player_stats, dated by
  his latest game for that team in player_fixture_ratings).

The newest piece of evidence wins: a player who played for Arsenal in August
and joined Al-Hilal in September has moved, even though Al-Hilal's games
aren't tracked. When it names a team other than the one he's registered to,
that is a mismatch.

A TransferX club is matched to its API-Football team by the team most of its
squad came from (the demo clubs were built from those squads), else by name.
"""
from __future__ import annotations

import re
import uuid
from collections import Counter, defaultdict
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

_YOUTH = re.compile(r"\s+(U\d{2}|II|B)$", re.I)


def _kind(t) -> str:
    """What a transfer row was: a loan, the end of one, or a transfer."""
    raw = f"{t.transfer_type or ''} {t.fee_display or ''}".lower()
    if "return from loan" in raw or "back from loan" in raw:
        return "loan_return"
    return "loan" if (t.transfer_type or "").lower() == "loan" else "transfer"


def _fee(raw: str | None) -> str | None:
    """API-Football's fee field also holds the transfer type ("Transfer",
    "Return from loan"); only an amount or a free transfer is a fee."""
    if not raw:
        return None
    if raw.lower().startswith("free"):
        return "Free"
    return raw if any(ch.isdigit() for ch in raw) else None


def current_season(today: date | None = None) -> str:
    from app.players.ledger import season_of

    return season_of(today or date.today())


def season_start(season: str) -> date:
    """The summer window opens in June, before the season's first game."""
    return date(int(season), 6, 1)


async def club_teams(db: AsyncSession) -> dict[uuid.UUID, str]:
    """{club_id: API-Football team id} for every TransferX club we can match."""
    from app.clubs.models import Club
    from app.players.models import Player
    from app.world.models import WorldTeam

    rows = (await db.execute(
        select(Player.current_club_id, WorldTeam.vendor_id)
        .join(WorldTeam, WorldTeam.id == Player.world_team_id)
        .where(Player.current_club_id.is_not(None))
    )).all()
    votes: dict[uuid.UUID, Counter] = defaultdict(Counter)
    for club_id, team in rows:
        votes[club_id][team] += 1
    out = {club_id: c.most_common(1)[0][0] for club_id, c in votes.items()}

    unmatched = [cid for cid in (await db.execute(select(Club.id))).scalars() if cid not in out]
    if unmatched:
        by_name = dict((await db.execute(
            select(func.lower(Club.name), Club.id).where(Club.id.in_(unmatched))
        )).all())
        for name, team in (await db.execute(
            select(func.lower(WorldTeam.name), WorldTeam.vendor_id).where(func.lower(WorldTeam.name).in_(list(by_name)))
        )).all():
            out.setdefault(by_name[name], team)
    return out


async def check(db: AsyncSession, players, *, today: date | None = None) -> dict[uuid.UUID, dict]:
    """{player_id: mismatch} for the players whose real-world club isn't the
    one TransferX has them registered to. Players with no club on TransferX,
    or a club we can't match to a team, aren't checked; a move staff have
    dismissed isn't reported again unless it points at a different team."""
    from app.clubs.models import Club
    from app.players.ledger import _countries
    from app.players.models import Contract, PlayerStatus, PlayerTransfer, RealWorldDismissal
    from app.stats.models import PlayerFixtureRating, PlayerStats
    from app.world.models import WorldLeague, WorldTeam

    players = [p for p in players if p.current_club_id is not None and p.status == PlayerStatus.CONTRACTED]
    if not players:
        return {}
    teams = await club_teams(db)
    players = [p for p in players if p.current_club_id in teams]
    if not players:
        return {}
    team_to_club = {team: club_id for club_id, team in teams.items()}
    ids = [p.id for p in players]
    season = current_season(today)
    start = season_start(season)

    transfers: dict = {}
    for t in (await db.execute(
        select(PlayerTransfer).where(PlayerTransfer.player_id.in_(ids), PlayerTransfer.transfer_date.is_not(None))
        .order_by(PlayerTransfer.transfer_date.desc())
    )).scalars():
        transfers.setdefault(t.player_id, t)
    contract_start = dict((await db.execute(
        select(Contract.player_id, Contract.start_date).where(Contract.player_id.in_(ids), Contract.is_active.is_(True))
    )).all())

    countries = await _countries(db)
    stats = (await db.execute(select(PlayerStats).where(
        PlayerStats.player_id.in_(ids), PlayerStats.season == season, PlayerStats.appearances > 0,
        PlayerStats.team_vendor_id.is_not(None),
    ))).scalars().all()
    # Rows the league sync stored before 2026-10-12 have no competition name.
    league_names = dict((await db.execute(select(WorldLeague.league_id, WorldLeague.name).where(
        WorldLeague.league_id.in_({r.league_id for r in stats if r.league_id and not r.league_name}))
    )).all())
    played: dict = defaultdict(dict)  # player -> team -> (name, logo)
    for r in stats:
        name = r.team_name or ""
        competition = r.league_name or league_names.get(r.league_id) or ""
        if _YOUTH.sub("", name).lower() in countries or competition.lower().startswith("friendlies"):
            continue
        played[r.player_id].setdefault(r.team_vendor_id, (name, r.team_logo))
    last_game = {(pid, team): day for pid, team, day in (await db.execute(
        select(PlayerFixtureRating.player_id, PlayerFixtureRating.team_vendor_id, func.max(PlayerFixtureRating.fixture_date))
        .where(PlayerFixtureRating.player_id.in_(ids), PlayerFixtureRating.fixture_date >= start)
        .group_by(PlayerFixtureRating.player_id, PlayerFixtureRating.team_vendor_id)
    )).all()}

    team_names = dict((await db.execute(
        select(WorldTeam.vendor_id, WorldTeam.name).where(WorldTeam.vendor_id.in_(set(teams.values())))
    )).all())
    seen = {team for by_team in played.values() for team in by_team} | {t.team_in_vendor_id for t in transfers.values()}
    crests = dict((await db.execute(
        select(WorldTeam.vendor_id, WorldTeam.crest_url).where(WorldTeam.vendor_id.in_({t for t in seen if t}))
    )).all())
    club_names = dict((await db.execute(select(Club.id, Club.name))).all())
    dismissed = set((await db.execute(
        select(RealWorldDismissal.player_id, RealWorldDismissal.real_team_vendor_id)
        .where(RealWorldDismissal.player_id.in_(ids))
    )).all())

    out = {}
    for p in players:
        registered = teams[p.current_club_id]
        registered_name = (team_names.get(registered) or club_names.get(p.current_club_id) or "").lower()
        evidence = []  # (date, priority, kind, team, name, logo, fee)
        for team, (name, logo) in played[p.id].items():
            day = last_game.get((p.id, team))
            evidence.append((day or start, 0, "playing", team, name, logo, None, day))
        t = transfers.get(p.id)
        began = contract_start.get(p.id)
        if t is not None and t.team_in_vendor_id and t.transfer_date >= start and (began is None or t.transfer_date > began):
            kind = _kind(t)
            evidence.append((t.transfer_date, 1, kind, t.team_in_vendor_id, t.team_in_name, t.team_in_crest_url,
                             t.fee_display, None))
        if not evidence:
            continue
        day, _, kind, team, name, logo, fee, last = max(evidence, key=lambda e: (e[0], e[1]))
        # His own club's youth or B side is still his club.
        if team == registered or _YOUTH.sub("", name or "").lower() == registered_name:
            continue
        if (p.id, team) in dismissed:
            continue
        moved = t if t is not None and t.team_in_vendor_id == team and t.transfer_date >= start else None
        if kind == "playing" and moved is not None:
            kind, fee = _kind(moved), moved.fee_display
        logo = logo or (moved.team_in_crest_url if moved is not None else None) or crests.get(team)
        moved_on = moved.transfer_date if moved is not None else None
        out[p.id] = {
            "kind": kind,  # transfer | loan | loan_return | playing (seen playing there; no transfer on record)
            "registered_club_id": str(p.current_club_id),
            "registered_club": club_names.get(p.current_club_id),
            "real_team_vendor_id": team,
            "real_club": name,
            "real_club_logo": logo,
            "real_club_on_transferx_id": str(team_to_club[team]) if team in team_to_club else None,
            "moved_on": moved_on.isoformat() if moved_on else None,
            "fee": _fee(fee) if kind == "transfer" else None,
            "last_played": max((d for (pid, tm), d in last_game.items() if pid == p.id and tm == team), default=None),
            "season": season,
        }
        if out[p.id]["last_played"] is not None:
            out[p.id]["last_played"] = out[p.id]["last_played"].isoformat()
    return out


async def list_moves(db: AsyncSession, *, today: date | None = None) -> dict:
    """Every contracted player whose real-world club differs from his
    TransferX one, for Admin → Real-world moves."""
    from app.players.models import Player, PlayerStatus

    players = (await db.execute(select(Player).where(
        Player.status == PlayerStatus.CONTRACTED, Player.current_club_id.is_not(None)))).scalars().all()
    found = await check(db, players, today=today)
    by_id = {p.id: p for p in players}
    blocked = await _blockers(db, found)
    rows = []
    for pid, m in found.items():
        p = by_id[pid]
        rows.append({"player_id": str(pid), "name": p.name, "photo_url": p.photo_url,
                     "position": getattr(p.position, "value", p.position) if p.position else None,
                     **m, "apply_blocked": blocked.get(pid)})
    rows.sort(key=lambda r: (r["registered_club"] or "", r["name"]))
    kinds = Counter(r["kind"] for r in rows)
    return {
        "season": current_season(today),
        "checked": len(players),
        "mismatches": rows,
        "counts": {"transfer": kinds["transfer"], "loan": kinds["loan"], "loan_return": kinds["loan_return"],
                   "playing": kinds["playing"],
                   "to_transferx_club": sum(1 for r in rows if r["real_club_on_transferx_id"])},
    }


# ── Acting on a move (TransferX staff) ───────────────────────────────────────

LOAN_OUTSIDE = ("A loan to a club outside TransferX doesn't change his registration: he's still "
                "{club}'s player. Dismiss it to stop it being reported.")
LOAN_INSIDE = ("A loan between TransferX clubs needs terms API-Football doesn't have (dates, wage split, "
               "options). Record it as a loan deal between the clubs, or dismiss it.")


async def _blockers(db: AsyncSession, moves: dict[uuid.UUID, dict]) -> dict[uuid.UUID, str]:
    """{player_id: why the move can't be applied}, for the moves that can't."""
    from app.deals.service import get_active_deals_for_players
    from app.loans.service import get_active_loans_for_players

    ids = list(moves)
    deals = await get_active_deals_for_players(db, ids)
    loans = await get_active_loans_for_players(db, ids)
    out = {}
    for pid, m in moves.items():
        deal = deals.get(pid)
        if deal is not None and deal.status.value in ("IN_PROGRESS", "PENDING_COMPLETION"):
            out[pid] = "He's in a deal on TransferX. Finish or collapse it first."
        elif pid in loans:
            out[pid] = "He's on loan on TransferX. End the loan first."
        elif m["kind"] == "loan":
            out[pid] = (LOAN_INSIDE if m["real_club_on_transferx_id"]
                        else LOAN_OUTSIDE.format(club=m["registered_club"] or "his club"))
    return out


async def _locked_player(db: AsyncSession, player_id: uuid.UUID):
    from app.players.models import Player

    player = (await db.execute(select(Player).where(Player.id == player_id).with_for_update())).scalar_one_or_none()
    if player is None:
        raise LookupError("Player not found")
    return player


async def apply_move(db: AsyncSession, admin, player_id: uuid.UUID, *, reason: str,
                     today: date | None = None) -> dict:
    """Correct a player's registration to match his real-world move, as
    TransferX staff. The move is re-checked here; the client's view of it is
    never trusted. His open offers, listings and enquiries are closed (the
    budget offers held is released), his TransferX contract ends, and either
    a contract at the TransferX club he joined starts (unconfirmed, for that
    club's "Check your squad") or he becomes a player at a club outside
    TransferX. Both clubs are told; the change is audited with the reason.
    No money moves. Raises ValueError when it can't be applied. Caller commits."""
    from app.admin import audit as admin_audit
    from app.clubs.models import Club
    from app.enquiries.models import Enquiry, EnquiryStatus
    from app.notifications import service as notif_service
    from app.notifications.models import NotificationType
    from app.offers.models import Offer, OfferStatus
    from app.offers.service import staff_withdraw_offer
    from app.players.models import Contract, PlayerStatus
    from app.sales.models import Sale, SaleStatus
    from app.sales.service import withdraw_sale
    from app.world.models import WorldTeam

    player = await _locked_player(db, player_id)
    move = (await check(db, [player], today=today)).get(player.id)
    if move is None:
        raise ValueError("Nothing to apply: his registration matches API-Football (or the move was dismissed).")
    blocked = (await _blockers(db, {player.id: move})).get(player.id)
    if blocked:
        raise ValueError(blocked)

    old_club_id = player.current_club_id
    new_club_id = uuid.UUID(move["real_club_on_transferx_id"]) if move["real_club_on_transferx_id"] else None
    real = move["real_club"] or "another club"
    note = f"{player.name} has moved to {real} in real life. {reason}"
    effective = date.fromisoformat(move["moved_on"]) if move["moved_on"] else (today or date.today())

    closed = {"offers": [], "sales": [], "enquiries": []}
    for offer in (await db.execute(select(Offer).where(
            Offer.player_id == player.id, Offer.status.in_([OfferStatus.SENT, OfferStatus.COUNTERED])))).scalars():
        await staff_withdraw_offer(db, offer, reason=note)
        closed["offers"].append(str(offer.id))
    for sale in (await db.execute(select(Sale).where(
            Sale.player_id == player.id, Sale.status == SaleStatus.OPEN))).scalars():
        await withdraw_sale(db, sale, None, staff_reason=note)
        closed["sales"].append(str(sale.id))
    for enquiry in (await db.execute(select(Enquiry).where(
            Enquiry.player_id == player.id, Enquiry.status == EnquiryStatus.OPEN))).scalars():
        enquiry.status = EnquiryStatus.CLOSED
        closed["enquiries"].append(str(enquiry.id))

    for contract in (await db.execute(select(Contract).where(
            Contract.player_id == player.id, Contract.is_active.is_(True)))).scalars():
        contract.is_active = False
        if contract.end_date is None or contract.end_date > effective:
            contract.end_date = effective
        contract.notes = ((contract.notes + " ") if contract.notes else "") + f"Ended by TransferX staff: moved to {real}."

    team = (await db.execute(select(WorldTeam).where(
        WorldTeam.vendor_id == move["real_team_vendor_id"]))).scalars().first()
    if new_club_id is not None:
        db.add(Contract(player_id=player.id, club_id=new_club_id, is_active=True, start_date=effective,
                        notes="Started by TransferX staff to match a real-world move; terms to confirm."))
        player.current_club_id = new_club_id
        player.status = PlayerStatus.CONTRACTED
        player.team_name = (await db.execute(select(Club.name).where(Club.id == new_club_id))).scalar_one()
    else:
        player.current_club_id = None
        player.status = PlayerStatus.EXTERNAL
        player.team_name = real
    player.world_team_id = team.id if team is not None else None
    await db.flush()

    details = {"player": player.name, "kind": move["kind"], "from_club_id": old_club_id,
               "from_club": move["registered_club"], "to_club": real, "to_club_id": new_club_id,
               "moved_on": move["moved_on"], "closed": closed}
    await admin_audit.record(
        db, admin, "real_world_move.applied", entity_type="player", entity_id=player.id, reason=reason,
        description=f"Moved {player.name} from {move['registered_club']} to {real} to match a real-world move",
        details=details,
    )
    await notif_service.notify_club(
        db, old_club_id, type=NotificationType.REGISTRATION_UPDATED, related_player_id=player.id,
        message=f"TransferX staff took {player.name} off your squad: he has joined {real}.",
        link=f"/players/market/{player.id}",
    )
    if new_club_id is not None:
        await notif_service.notify_club(
            db, new_club_id, type=NotificationType.REGISTRATION_UPDATED, related_player_id=player.id,
            message=f"TransferX staff added {player.name} to your squad. Check his contract details.",
            link="/club/squad-check",
        )
    return {"player_id": str(player.id), "name": player.name, **details}


async def dismiss_move(db: AsyncSession, admin, player_id: uuid.UUID, *, reason: str,
                       today: date | None = None) -> dict:
    """Leave the registration as it is and stop reporting this move (until
    the evidence points at another team). Audited. Caller commits."""
    from app.admin import audit as admin_audit
    from app.players.models import RealWorldDismissal

    player = await _locked_player(db, player_id)
    move = (await check(db, [player], today=today)).get(player.id)
    if move is None:
        raise ValueError("Nothing to dismiss: there's no move reported for him.")
    db.add(RealWorldDismissal(player_id=player.id, real_team_vendor_id=move["real_team_vendor_id"],
                              real_club=move["real_club"], reason=reason, dismissed_by_user_id=admin.id))
    await db.flush()
    await admin_audit.record(
        db, admin, "real_world_move.dismissed", entity_type="player", entity_id=player.id, reason=reason,
        description=f"Left {player.name} registered to {move['registered_club']} despite a move to {move['real_club']}",
        details={"player": player.name, "kind": move["kind"], "registered_club": move["registered_club"],
                 "real_club": move["real_club"]},
    )
    return {"player_id": str(player.id), "name": player.name, "dismissed": True}


# ── Telling the club ─────────────────────────────────────────────────────────

ALERT_NAMES = 3  # players named in the message; the rest are counted


async def alert_clubs(db: AsyncSession, *, today: date | None = None) -> int:
    """Tell each club which of its players API-Football has elsewhere, so a
    sporting director doesn't plan around a player who has gone. One
    notification per club listing them all, sent again only when the list
    gains a player (the group key is the set of moves); a move staff apply
    or dismiss drops out on its own. Returns how many clubs were told."""
    import hashlib

    from app.notifications import service as notif_service
    from app.notifications.models import NotificationType

    by_club: dict[str, list[dict]] = defaultdict(list)
    for move in (await list_moves(db, today=today))["mismatches"]:
        by_club[move["registered_club_id"]].append(move)
    told = 0
    for club_id, moves in by_club.items():
        moves.sort(key=lambda m: m["name"])
        key = hashlib.sha1("|".join(sorted(f"{m['player_id']}:{m['real_team_vendor_id']}" for m in moves))
                           .encode()).hexdigest()[:16]
        named = ", ".join(f"{m['name']} ({m['real_club'] or 'another club'})" for m in moves[:ALERT_NAMES])
        more = len(moves) - ALERT_NAMES
        n = len(moves)
        message = (f"API-Football has {n} of your players at other clubs: {named}"
                   + (f" and {more} more" if more > 0 else "") + ". "
                   "TransferX staff will update your squad; until then they're still listed in it.")
        await notif_service.notify_club(
            db, uuid.UUID(club_id), type=NotificationType.REAL_WORLD_MOVES, message=message,
            link=f"/players/market/{moves[0]['player_id']}" if n == 1 else "/club",
            title="Players moved in real life", group_key=f"real-world:{key}", once=True,
        )
        told += 1
    return told
