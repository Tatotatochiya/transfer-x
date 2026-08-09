#!/usr/bin/env python
"""
Generate demo scenarios for TransferX — deals parked at every lifecycle stage.

Closes DEMO_READINESS_AUDIT C1 (no deal is in a demonstrable in-progress stage).
See docs/feature_spec/demo-scenario-generator.md for the full specification.

Every scenario is built by calling the same service functions the API calls, in
the order a real user would — never by writing a stage directly. That is what
gives each generated deal a populated audit timeline, real budget movement, and
commission records. A hand-inserted deal renders with an empty timeline, which
is the exact impression this script exists to fix.

Usage (inside Docker):
    docker compose exec api python scripts/seed_demo.py
    docker compose exec api python scripts/seed_demo.py --dry-run
    docker compose exec api python scripts/seed_demo.py --only D2,D3
    docker compose exec api python scripts/seed_demo.py --reset
    docker compose exec api python scripts/seed_demo.py --refresh

Usage (local venv, from backend/ dir):
    python scripts/seed_demo.py
"""

import argparse
import asyncio
import json
import random
import sys
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

# Allow running from the backend/ directory or the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# SQLAlchemy resolves relationship() targets by name against the mapper registry,
# so every model module must be imported before the first query — same reason
# migrations/env.py carries its own import block. Importing the modules (rather
# than individual names) keeps this from drifting as models are added.
import app.agents.models  # noqa: F401
import app.analytics.models  # noqa: F401
import app.approvals.models  # noqa: F401
import app.audit.models  # noqa: F401
import app.auth.models  # noqa: F401
import app.clubs.models  # noqa: F401
import app.deals.models  # noqa: F401
import app.fixtures.models  # noqa: F401
import app.mandates.models  # noqa: F401
import app.notifications.models  # noqa: F401
import app.offers.models  # noqa: F401
import app.players.models  # noqa: F401
import app.sales.models  # noqa: F401
import app.scouting.models  # noqa: F401
import app.stats.models  # noqa: F401
import app.transfer_window.models  # noqa: F401
import app.valuation.models  # noqa: F401
import app.verification.models  # noqa: F401
import app.world.models  # noqa: F401

# deals/offers/sales service modules do `from app import clubs as clubs_module`
# and then reach for `clubs_module.service.*` at call time. That only resolves if
# app.clubs.service has already been imported by someone — in the running app the
# routers do it. A standalone script has to import it explicitly.
import app.clubs.service  # noqa: F401

from app.agents.models import AgreementStatus
from app.auth.models import AgentProfile, User
from app.clubs.models import Club
from app.config import settings
from app.deals import service as deals_service
from app.deals.models import Deal, DealStage, DealType, MedicalStatus
from app.mandates.models import Mandate, MandateStatus
from app.offers import service as offers_service
from app.players import service as players_service
from app.players.models import Player
from app.sales import service as sales_service
from app.sales.models import SaleType

DEFAULT_SEED = 20260808
MARKER_TABLE = "demo_seed_records"

# The three clubs with real budgets. The other six are £0 test residue.
ARSENAL, CHELSEA, LIVERPOOL = "Arsenal", "Chelsea", "Liverpool"

# Per-club ceiling on what generated activity may reserve/commit, so a presenter
# can still place bids live without hitting a budget rejection mid-demo.
BUDGET_HEADROOM = Decimal("0.40")

# Scenario definitions. `mandated` decides the entry stage: a player with an
# active mandate lands the deal in AGENT_NEGOTIATION via
# offers/service.py::maybe_invite_agent_for_deal; without one it stays AGREEMENT.
SCENARIOS = [
    {
        "id": "D1", "stage": "AGREEMENT", "seller": LIVERPOOL, "buyer": ARSENAL,
        "mandated": False, "fee_cap": Decimal("45000000"),
        "desc": "Fresh agreement, terms still open",
    },
    {
        "id": "D2", "stage": "AGENT_NEGOTIATION", "seller": CHELSEA, "buyer": ARSENAL,
        "mandated": True, "fee_cap": Decimal("40000000"),
        "desc": "Agent has proposed commission, club yet to respond",
    },
    {
        "id": "D3", "stage": "PERSONAL_TERMS", "seller": ARSENAL, "buyer": CHELSEA,
        "mandated": True, "fee_cap": Decimal("35000000"),
        "desc": "Personal terms on the table, awaiting player consent",
    },
    {
        "id": "D4", "stage": "PAPERWORK", "seller": LIVERPOOL, "buyer": CHELSEA,
        "mandated": True, "fee_cap": Decimal("30000000"),
        "desc": "Consented and through medical, with TransferX",
    },
    {
        "id": "D5", "stage": "CONFIRMED", "seller": CHELSEA, "buyer": LIVERPOOL,
        "mandated": False, "fee_cap": Decimal("30000000"),
        "desc": "Ready to execute, SLA running",
    },
    {
        "id": "D6", "stage": "COLLAPSED", "seller": ARSENAL, "buyer": LIVERPOOL,
        "mandated": False, "fee_cap": Decimal("25000000"),
        "desc": "Collapsed — player declined personal terms",
    },
]


# ── Marker table ──────────────────────────────────────────────────────────────
# Created by the script rather than an Alembic migration: demo tooling should not
# add a table to the production schema or the migration chain (still clean at
# 0059). Deviation from the spec's "dedicated marker table via migration".

async def ensure_marker_table(db: AsyncSession) -> None:
    await db.execute(text(f"""
        CREATE TABLE IF NOT EXISTS {MARKER_TABLE} (
            id          uuid PRIMARY KEY,
            run_id      uuid NOT NULL,
            entity_type varchar(32) NOT NULL,
            entity_id   uuid NOT NULL,
            payload     jsonb,
            created_at  timestamptz NOT NULL DEFAULT now()
        )
    """))
    # Older runs created the table without payload.
    await db.execute(text(f"ALTER TABLE {MARKER_TABLE} ADD COLUMN IF NOT EXISTS payload jsonb"))


async def track(
    db: AsyncSession, run_id: uuid.UUID, entity_type: str, entity_id: uuid.UUID,
    payload: dict | None = None,
) -> None:
    await db.execute(
        text(f"INSERT INTO {MARKER_TABLE} (id, run_id, entity_type, entity_id, payload) "
             f"VALUES (:i, :r, :t, :e, CAST(:p AS jsonb))"),
        {"i": uuid.uuid4(), "r": run_id, "t": entity_type, "e": entity_id,
         "p": json.dumps(payload) if payload is not None else None},
    )


async def tracked_ids(db: AsyncSession, entity_type: str) -> list[uuid.UUID]:
    r = await db.execute(
        text(f"SELECT entity_id FROM {MARKER_TABLE} WHERE entity_type = :t"),
        {"t": entity_type},
    )
    return [row[0] for row in r]


async def tracked_payloads(db: AsyncSession, entity_type: str) -> list[tuple]:
    r = await db.execute(
        text(f"SELECT entity_id, payload FROM {MARKER_TABLE} WHERE entity_type = :t"),
        {"t": entity_type},
    )
    return [(row[0], row[1]) for row in r]


# ── Lookups ───────────────────────────────────────────────────────────────────

async def club_by_name(db: AsyncSession, name: str) -> Club:
    r = await db.execute(select(Club).where(Club.name == name))
    club = r.scalar_one_or_none()
    if club is None:
        raise SystemExit(f"Club {name!r} not found — reference data missing. Restore the snapshot first.")
    return club


async def superuser(db: AsyncSession) -> User:
    r = await db.execute(select(User).where(User.is_superuser.is_(True)).limit(1))
    u = r.scalar_one_or_none()
    if u is None:
        raise SystemExit("No superuser found — PAPERWORK -> CONFIRMED is staff-only. "
                         "Create one with scripts/create_superuser.py.")
    return u


async def club_owner(db: AsyncSession, club: Club) -> User:
    r = await db.execute(select(User).where(User.id == club.user_id))
    return r.scalar_one()


async def agent_user(db: AsyncSession, agent_profile_id: uuid.UUID) -> User:
    r = await db.execute(
        select(User).join(AgentProfile, AgentProfile.user_id == User.id)
        .where(AgentProfile.id == agent_profile_id)
    )
    return r.scalar_one()


async def _candidate_players(db: AsyncSession, club: Club, *, mandated: bool, exclude: set) -> list:
    """Players owned by `club`, free of active deals/sales, with or without a mandate.

    Ordered by valuation desc (nulls last) so recognisable names come first.
    """
    mandate_clause = "EXISTS" if mandated else "NOT EXISTS"
    r = await db.execute(text(f"""
        SELECT p.id, p.name,
               (SELECT pv.fair_value FROM player_valuations pv
                 WHERE pv.player_id = p.id ORDER BY pv.computed_at DESC LIMIT 1) AS val
        FROM players p
        WHERE p.current_club_id = :club_id
          AND {mandate_clause} (SELECT 1 FROM mandates m
                                 WHERE m.player_id = p.id AND m.status = 'ACTIVE')
          AND NOT EXISTS (SELECT 1 FROM deals d WHERE d.player_id = p.id
                           AND d.status IN ('IN_PROGRESS','PENDING_COMPLETION'))
          AND NOT EXISTS (SELECT 1 FROM sales s WHERE s.player_id = p.id AND s.status = 'OPEN')
        ORDER BY val DESC NULLS LAST
    """), {"club_id": club.id})
    return [row for row in r if row[0] not in exclude]


async def active_mandate_for(db: AsyncSession, player_id: uuid.UUID) -> Mandate:
    """The mandate maybe_invite_agent_for_deal will pick: exclusive first, then newest."""
    r = await db.execute(
        select(Mandate)
        .where(Mandate.player_id == player_id, Mandate.status == MandateStatus.ACTIVE)
        .order_by(Mandate.exclusive.desc(), Mandate.created_at.desc())
        .limit(1)
    )
    return r.scalar_one()


# ── Money ─────────────────────────────────────────────────────────────────────

def derive_fee(valuation, cap: Decimal, rng: random.Random) -> Decimal:
    """Fee derived from the model valuation, alternating above/below so the
    fair-value divergence badge visibly does something. Clamped to the cap."""
    if valuation:
        multiplier = Decimal(str(rng.choice([0.82, 0.94, 1.12, 1.25])))
        fee = (Decimal(str(valuation)) * multiplier)
    else:
        fee = cap * Decimal("0.7")
    fee = min(fee, cap)
    fee = max(fee, Decimal("1000000"))
    # Round to the nearest £100k so figures read like real transfer fees.
    return (fee / Decimal("100000")).quantize(Decimal("1")) * Decimal("100000")


def derive_wage(fee: Decimal, rng: random.Random) -> Decimal:
    """Weekly wage roughly proportional to fee, rounded to £5k."""
    base = fee / Decimal("250")
    jitter = Decimal(str(rng.uniform(0.85, 1.15)))
    wage = base * jitter
    wage = max(wage, Decimal("20000"))
    return (wage / Decimal("5000")).quantize(Decimal("1")) * Decimal("5000")


async def check_budget_headroom(db: AsyncSession, plan: list) -> None:
    """Fail before writing anything if a buyer's planned spend breaches headroom."""
    by_buyer: dict = {}
    for step in plan:
        by_buyer.setdefault(step["buyer"], Decimal("0"))
        by_buyer[step["buyer"]] += step["fee"]

    for club_name, total in by_buyer.items():
        club = await club_by_name(db, club_name)
        r = await db.execute(text(
            "SELECT transfer_budget_total, transfer_reserved, transfer_committed "
            "FROM club_finances WHERE club_id = :c"), {"c": club.id})
        row = r.first()
        if row is None:
            raise SystemExit(f"{club_name} has no club_finances row.")
        budget, reserved, committed = row
        ceiling = Decimal(str(budget)) * BUDGET_HEADROOM
        projected = Decimal(str(reserved)) + Decimal(str(committed)) + total
        if projected > ceiling:
            raise SystemExit(
                f"{club_name}: planned spend would breach the {BUDGET_HEADROOM:.0%} headroom "
                f"(projected £{projected:,.0f} vs ceiling £{ceiling:,.0f}). "
                f"Lower a fee_cap or run --reset first."
            )


# ── Scenario construction ─────────────────────────────────────────────────────

async def build_scenario(
    db: AsyncSession, run_id: uuid.UUID, spec: dict, plan: dict, *, verbose: bool
) -> Deal:
    """Create sale -> offer -> accept, then advance to the target stage."""
    seller, buyer = plan["seller_club"], plan["buyer_club"]
    player_id, player_name = plan["player_id"], plan["player_name"]
    fee, wage = plan["fee"], plan["wage"]

    def log(msg: str) -> None:
        if verbose:
            print(f"    {msg}")

    staff = await superuser(db)
    seller_owner = await club_owner(db, seller)
    buyer_owner = await club_owner(db, buyer)

    # 0. Snapshot the player's pre-run state. If a demo advances a deal all the
    #    way to COMPLETED, _complete_deal swaps the player's contract and clears
    #    open_to_offers — neither of which is recoverable from the deal row once
    #    it's deleted (contracts have no FK to deals). Recording it here is what
    #    makes --reset able to put the player back.
    pre = (await db.execute(text(
        "SELECT current_club_id, open_to_offers, status FROM players WHERE id = :p"
    ), {"p": player_id})).first()
    await track(db, run_id, "PLAYER_STATE", player_id, {
        "current_club_id": str(pre[0]) if pre and pre[0] else None,
        "open_to_offers": bool(pre[1]) if pre else False,
        "status": str(pre[2]) if pre and pre[2] else None,
    })
    await db.commit()

    # 1. Seller lists the player.
    sale = await sales_service.create_sale(
        db,
        player_id=player_id,
        seller_club_id=seller.id,
        sale_type=SaleType.OPEN_TO_OFFERS,
        asking_price=fee,
        notes=f"{spec['desc']}",
    )
    await db.flush()
    await track(db, run_id, "SALE", sale.id)
    await db.commit()
    log(f"listed {player_name} (asking £{fee:,.0f})")

    # 2. Buyer offers against the listing. Reserves budget.
    offer = await offers_service.create_offer(
        db,
        player_id=player_id,
        from_club_id=buyer.id,
        to_club_id=seller.id,
        sale_id=sale.id,
        fee_amount=fee,
        wage_weekly=wage,
        contract_years=4,
        expires_at=datetime.now(timezone.utc) + timedelta(days=14),
    )
    await db.flush()
    await track(db, run_id, "OFFER", offer.id)
    await db.commit()
    log(f"{buyer.name} offered £{fee:,.0f} (£{wage:,.0f}/wk)")

    # 3. Seller accepts -> Deal. maybe_invite_agent_for_deal decides the entry
    #    stage: AGENT_NEGOTIATION if the player has an active mandate, else
    #    AGREEMENT. This is why player selection drives stage targeting.
    deal = await offers_service.accept_offer(db, offer, actor_club_id=seller.id)
    await db.flush()
    await track(db, run_id, "DEAL", deal.id)
    await db.commit()
    log(f"accepted -> deal at {deal.stage.value}")

    target = spec["stage"]
    if target == "AGREEMENT":
        return deal

    # ── Mandated path: agent proposes commission ──────────────────────────────
    if spec["mandated"]:
        if deal.stage != DealStage.AGENT_NEGOTIATION:
            raise SystemExit(
                f"{spec['id']}: expected AGENT_NEGOTIATION but got {deal.stage.value}. "
                f"{player_name} may have lost their mandate mid-run."
            )
        mandate = await active_mandate_for(db, player_id)
        ag_user = await agent_user(db, mandate.agent_id)
        # commission_pct is a fraction, not a percentage: Numeric(5,4), and
        # upsert_negotiation_terms derives the amount as `pct * agreed_fee`
        # directly. 0.05 means 5%; passing 5 would bill 500% of the fee.
        commission_pct = Decimal("0.05")
        await deals_service.upsert_negotiation_terms(
            db, deal, mandate.agent_id,
            {"commission_pct": commission_pct, "commission_payer": "BUYER"},
            actor_user_id=ag_user.id,
        )
        await db.commit()
        log(f"agent proposed {commission_pct * 100:.0f}% commission")

        if target == "AGENT_NEGOTIATION":
            return deal

        # Buying club agrees, then the agent advances the stage.
        await deals_service.club_respond_to_negotiation(
            db, deal, buyer.id, AgreementStatus.AGREED, actor_user_id=buyer_owner.id,
        )
        await db.commit()
        log(f"{buyer.name} agreed commission")

        await deals_service.advance_deal(
            db, deal, is_mandated_agent=True, actor_user_id=ag_user.id,
        )
        await db.commit()
        log(f"advanced -> {deal.stage.value}")
        terms_agent_id = mandate.agent_id
        consent_user = ag_user
    else:
        # ── Unmandated path: club advances straight to personal terms ─────────
        await deals_service.advance_deal(
            db, deal, actor_club_id=buyer.id, actor_user_id=buyer_owner.id,
        )
        await db.commit()
        log(f"advanced -> {deal.stage.value}")
        terms_agent_id = None
        # No agent and (almost always) no player account, so only a superuser can
        # consent. See the spec's edge-case note — this is a real constraint, not
        # a shortcut: without it an unmandated deal cannot legitimately reach
        # PAPERWORK at all.
        consent_user = staff

    # ── Personal terms ────────────────────────────────────────────────────────
    await deals_service.set_personal_terms(
        db, deal,
        agent_profile_id=terms_agent_id,
        wage_weekly=wage,
        signing_bonus=(fee / Decimal("20")).quantize(Decimal("1")),
        length_years=4,
        actor_user_id=(consent_user.id if terms_agent_id else staff.id),
    )
    await db.commit()
    log("personal terms proposed")

    if target == "PERSONAL_TERMS":
        return deal

    # ── Consent (or decline, for the collapse scenario) ───────────────────────
    if target == "COLLAPSED":
        await deals_service.player_consent_to_terms(
            db, deal, AgreementStatus.DECLINED, actor_user_id=consent_user.id,
        )
        await db.commit()
        log(f"player declined -> {deal.status.value}")
        return deal

    await deals_service.player_consent_to_terms(
        db, deal, AgreementStatus.AGREED, actor_user_id=consent_user.id,
    )
    await db.commit()
    log("player consented")

    await deals_service.advance_deal(
        db, deal, actor_club_id=buyer.id, actor_user_id=buyer_owner.id,
    )
    await db.commit()
    log(f"advanced -> {deal.stage.value}")

    # A PASSED medical so the panel isn't empty on the paperwork demo.
    await deals_service.upsert_medical_check(
        db, deal, status=MedicalStatus.PASSED,
        notes="Club medical completed. No issues found.",
        is_staff=True, actor_user_id=staff.id,
    )
    await db.commit()
    log("medical recorded (PASSED)")

    if target == "PAPERWORK":
        return deal

    # PAPERWORK -> CONFIRMED is staff-only; also stamps the SLA deadline.
    await deals_service.advance_deal(db, deal, is_staff=True, actor_user_id=staff.id)
    await db.commit()
    log(f"advanced -> {deal.stage.value} (status {deal.status.value})")
    return deal


# ── Reset ─────────────────────────────────────────────────────────────────────

async def _reverse_completed_deal(db: AsyncSession, deal: Deal, *, verbose: bool) -> None:
    """Undo the finance half of _complete_deal.

    Completion moves the buyer's fee committed -> spent and credits the seller's
    budget total; deleting the deal row afterwards would leave both permanently
    skewed. The contract half is undone in _restore_players, which works from the
    pre-run snapshot rather than trying to infer what the contract used to be.

    Mirrors app/deals/service.py::_complete_deal — keep the two in step.
    """
    fee = (deal.loan_fee if deal.deal_type == DealType.LOAN and deal.loan_fee is not None
           else deal.agreed_fee) or Decimal("0")
    new_wage = deal.agreed_wage_weekly or Decimal("0")

    has_instalments = (await db.execute(
        text("SELECT count(*) FROM deal_instalments WHERE deal_id = :d"), {"d": deal.id}
    )).scalar_one() or 0

    if fee > 0 and not has_instalments:
        # Buyer: undo committed -> spent. The whole deal is being erased, so the
        # fee returns to free budget rather than back into committed.
        await db.execute(text(
            "UPDATE club_finances SET transfer_spent = GREATEST(0, transfer_spent - :f) "
            "WHERE club_id = :c"), {"f": fee, "c": deal.buyer_club_id})
        if deal.seller_club_id:
            await db.execute(text(
                "UPDATE club_finances SET transfer_budget_total = transfer_budget_total - :f "
                "WHERE club_id = :c"), {"f": fee, "c": deal.seller_club_id})

    if new_wage > 0:
        await db.execute(text(
            "UPDATE club_finances SET wage_reserved_weekly = GREATEST(0, wage_reserved_weekly - :w) "
            "WHERE club_id = :c"), {"w": new_wage, "c": deal.buyer_club_id})

    if verbose:
        print(f"    reversed completed deal {deal.id} (fee £{fee:,.0f})")


async def _restore_players(db: AsyncSession, *, verbose: bool) -> None:
    """Put every touched player back to their pre-run club, status and offer flag.

    Restores the recorded snapshot verbatim rather than deriving state via
    players_service.normalize_player_status. That distinction matters: this
    database assigns squads through Player.current_club_id with almost no
    contract rows behind them (Chelsea has 25 squad players and 0 contracts), so
    deriving club from active contracts would strip the affiliation off every
    player it touched. Reverting means restoring what was there, not recomputing
    what the data model says should have been.

    Safe to run after a reset in which no deal ever completed — it simply writes
    back values that already match.
    """
    for player_id, payload in await tracked_payloads(db, "PLAYER_STATE"):
        if not payload:
            continue
        prior_club = payload.get("current_club_id")
        prior_open = payload.get("open_to_offers", False)
        prior_status = payload.get("status")

        r = await db.execute(select(Player).where(Player.id == player_id))
        player = r.scalar_one_or_none()
        if player is None:
            continue

        if prior_club is not None:
            prior_club_id = uuid.UUID(prior_club)
            # Drop any contract completion created with a different club...
            res = await db.execute(text(
                "DELETE FROM contracts WHERE player_id = :p AND club_id <> :c AND is_active = true"
            ), {"p": player_id, "c": prior_club_id})
            # ...and reinstate the one it deactivated, where one existed at all.
            await db.execute(text(
                "UPDATE contracts SET is_active = true WHERE player_id = :p AND club_id = :c"
            ), {"p": player_id, "c": prior_club_id})
            if verbose and res.rowcount:
                print(f"    restored {player.name} to their pre-run club")
            await db.execute(text(
                "UPDATE players SET current_club_id = :c WHERE id = :p"
            ), {"c": prior_club_id, "p": player_id})
        else:
            await db.execute(text(
                "UPDATE players SET current_club_id = NULL WHERE id = :p"), {"p": player_id})

        if prior_status:
            await db.execute(text(
                "UPDATE players SET status = CAST(:s AS playerstatus) WHERE id = :p"),
                {"s": prior_status, "p": player_id})
        await db.execute(text(
            "UPDATE players SET open_to_offers = :o WHERE id = :p"),
            {"o": prior_open, "p": player_id})


async def reset(db: AsyncSession, *, verbose: bool) -> None:
    """Remove generated records and release the budget they moved.

    Deal children (personal_terms, medical_checks, agent_negotiations,
    agent_commissions, agent_deal_invitations, clauses, instalments) and sale/offer
    children (bids, offer_events) all cascade, so deleting the three tracked
    entity types is sufficient. Order matters: deals reference offers.
    """
    await ensure_marker_table(db)
    deal_ids = await tracked_ids(db, "DEAL")
    offer_ids = await tracked_ids(db, "OFFER")
    sale_ids = await tracked_ids(db, "SALE")

    if not (deal_ids or offer_ids or sale_ids):
        print("Nothing to reset — no tracked demo records found.")
        return

    # Release budget still held by generated activity before deleting the rows
    # that explain it, otherwise clubs silently leak budget across reseed cycles.
    for deal_id in deal_ids:
        r = await db.execute(select(Deal).where(Deal.id == deal_id))
        deal = r.scalar_one_or_none()
        if deal is None:
            continue
        if deal.status.value in ("IN_PROGRESS", "PENDING_COMPLETION"):
            try:
                await deals_service.collapse_deal(
                    db, deal, actor_club_id=deal.buyer_club_id, is_staff=True,
                )
                if verbose:
                    print(f"    released budget for deal {deal_id}")
            except ValueError:
                pass
        elif deal.status.value == "COMPLETED":
            await _reverse_completed_deal(db, deal, verbose=verbose)
    await db.commit()

    # Offers still holding a reservation (never accepted) must be released too.
    for offer_id in offer_ids:
        offer = await offers_service.get_offer_by_id(db, offer_id)
        if offer is not None and offer.reserved_transfer_amount and offer.reserved_transfer_amount > 0:
            try:
                await offers_service.withdraw_offer(db, offer, actor_club_id=offer.from_club_id)
                if verbose:
                    print(f"    released reservation on offer {offer_id}")
            except (ValueError, PermissionError):
                pass
    await db.commit()

    # Notifications reference deals by link; audit events by entity_id.
    all_ids = [str(i) for i in deal_ids + offer_ids + sale_ids]
    if all_ids:
        await db.execute(
            text("DELETE FROM audit_events WHERE entity_id = ANY(:ids)"),
            {"ids": [uuid.UUID(i) for i in all_ids]},
        )
        for deal_id in deal_ids:
            await db.execute(
                text("DELETE FROM notifications WHERE link LIKE :pat"),
                {"pat": f"%{deal_id}%"},
            )

    for deal_id in deal_ids:
        await db.execute(text("DELETE FROM deals WHERE id = :i"), {"i": deal_id})
    for offer_id in offer_ids:
        await db.execute(text("DELETE FROM offers WHERE id = :i"), {"i": offer_id})
    for sale_id in sale_ids:
        await db.execute(text("DELETE FROM sales WHERE id = :i"), {"i": sale_id})

    # After the deals are gone, put the players back. Order matters: contracts
    # must be rewritten with no live deal still referencing the transfer.
    await _restore_players(db, verbose=verbose)

    await db.execute(text(f"DELETE FROM {MARKER_TABLE}"))
    await db.commit()
    print(f"Reset: removed {len(deal_ids)} deals, {len(offer_ids)} offers, {len(sale_ids)} sales.")


# ── Planning ──────────────────────────────────────────────────────────────────

async def build_plan(db: AsyncSession, specs: list, rng: random.Random) -> list:
    """Resolve clubs, players and money for every scenario before writing anything."""
    used: set = set()
    plan = []
    for spec in specs:
        seller = await club_by_name(db, spec["seller"])
        buyer = await club_by_name(db, spec["buyer"])
        candidates = await _candidate_players(db, seller, mandated=spec["mandated"], exclude=used)
        if not candidates:
            kind = "mandated" if spec["mandated"] else "unmandated"
            raise SystemExit(
                f"{spec['id']}: no available {kind} player at {seller.name}. "
                f"Run --reset, or create a mandate for one of their squad."
            )
        # Take from the top few by valuation so names are recognisable, but let the
        # seed choose which — deterministic per seed, varied across seeds.
        pick = rng.choice(candidates[:min(5, len(candidates))])
        player_id, player_name, valuation = pick[0], pick[1], pick[2]
        used.add(player_id)
        fee = derive_fee(valuation, spec["fee_cap"], rng)
        plan.append({
            "spec": spec,
            "seller_club": seller, "buyer_club": buyer, "seller": spec["seller"], "buyer": spec["buyer"],
            "player_id": player_id, "player_name": player_name,
            "fee": fee, "wage": derive_wage(fee, rng),
        })
    return plan


# ── Entry point ───────────────────────────────────────────────────────────────

async def main(args) -> None:
    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as db:
        if args.reset or args.refresh:
            await reset(db, verbose=args.verbose)
            if args.reset:
                await engine.dispose()
                return

        await ensure_marker_table(db)
        await db.commit()

        specs = SCENARIOS
        if args.only:
            wanted = {s.strip().upper() for s in args.only.split(",")}
            specs = [s for s in SCENARIOS if s["id"] in wanted]
            if not specs:
                raise SystemExit(f"No scenarios matched {args.only!r}. Known: "
                                 f"{', '.join(s['id'] for s in SCENARIOS)}")

        rng = random.Random(args.seed)
        plan = await build_plan(db, specs, rng)
        await check_budget_headroom(db, plan)

        print(f"\nPlan (seed {args.seed}):\n")
        for p in plan:
            s = p["spec"]
            print(f"  {s['id']}  {s['stage']:<18} {p['player_name']:<20} "
                  f"{p['seller']} -> {p['buyer']:<10} £{p['fee']:>12,.0f}  £{p['wage']:,.0f}/wk")

        if args.dry_run:
            print("\n--dry-run: nothing written.\n")
            await engine.dispose()
            return

        run_id = uuid.uuid4()
        print(f"\nBuilding (run {run_id}):\n")
        built = []
        for p in plan:
            s = p["spec"]
            print(f"  {s['id']} {s['stage']} — {p['player_name']}")
            deal = await build_scenario(db, run_id, s, p, verbose=args.verbose)
            built.append((s, deal))

        print("\nDone:\n")
        for s, deal in built:
            print(f"  {s['id']}  {deal.stage.value:<18} {deal.status.value:<18} /deals/{deal.id}")
        print()

    await engine.dispose()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Generate TransferX demo scenarios.")
    ap.add_argument("--reset", action="store_true", help="Remove generated demo data and exit")
    ap.add_argument("--refresh", action="store_true", help="Reset, then generate again")
    ap.add_argument("--only", type=str, help="Comma-separated scenario ids (e.g. D2,D3)")
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED, help="RNG seed for reproducible picks")
    ap.add_argument("--dry-run", action="store_true", help="Print the plan without writing")
    ap.add_argument("--verbose", action="store_true", help="Log every service call")
    asyncio.run(main(ap.parse_args()))
