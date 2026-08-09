---
title: "Demo Scenario Generator"
last_updated: 2026-08-08
status: Active
owner: "TODO — assign a Product Owner"
---

# Demo Scenario Generator

## Purpose

A re-runnable script that populates the database with a complete, realistic demo surface — deals parked at **every** lifecycle stage, plus live market activity — built entirely from the clubs, players, and agents that already exist.

This closes [`DEMO_READINESS_AUDIT.md`](../DEMO_READINESS_AUDIT.md) findings **C1** (no deal is in a demonstrable in-progress stage) and **C2** (no reproducible demo state). Those are the audit's top two blockers and share this one work item.

## Scope

In scope: a `scripts/seed_demo.py` that creates transactional demo state — sales, bids, offers, deals at each stage, and the supporting records that make each stage's UI panels non-empty — plus a matching teardown.

Out of scope:
- **Creating players, clubs, or world data.** Those already exist (7,914 players, 11 leagues, 3 real clubs) and are the responsibility of `sync_leagues.py` / `populate_world_teams.py`. This generator consumes them.
- **The database snapshot itself.** C2 also calls for a committed `pg_dump`; that is a separate, complementary artifact — see [Relationship to the snapshot](#relationship-to-the-snapshot).
- Fixing any audit finding other than C1/C2.

## Table of Contents

- [Design principles](#design-principles)
- [Available raw material](#available-raw-material)
- [How stage targeting actually works](#how-stage-targeting-actually-works)
- [Stage preconditions reference](#stage-preconditions-reference)
- [Scenario catalogue](#scenario-catalogue)
- [Command-line interface](#command-line-interface)
- [Tagging and teardown](#tagging-and-teardown)
- [Budget safety](#budget-safety)
- [Edge cases and gotchas](#edge-cases-and-gotchas)
- [Phasing](#phasing)
- [Success criteria](#success-criteria)
- [Relationship to the snapshot](#relationship-to-the-snapshot)
- [Related documents](#related-documents)

## Design principles

### 1. Drive the real service layer — never `INSERT` a deal into a stage

This is the single most important decision in this spec.

It is tempting to write rows directly: set `deal.stage = 'PAPERWORK'` and move on. **Don't.** A deal is not just a stage column — reaching `PAPERWORK` legitimately also produces an `AgentNegotiation` with agreed commission, a `PENDING` `AgentCommission` row, a `PersonalTerms` row with recorded consent, reserved-then-committed club budget, and a full `AuditEvent` trail with resolved actor labels.

A hand-inserted deal renders in the UI with **an empty timeline, no commission, and no consent record** — which is precisely the "this product has never done a transfer" impression C1 exists to fix. Worse, it can produce states the real state machine considers impossible, so the demo would break the moment anyone clicks *Advance*.

Every scenario must therefore be produced by calling the same service functions the API calls, in the same order a real user would, committing between steps. The generator is effectively a scripted user.

### 2. Deterministic

Seed the RNG from a fixed constant (overridable via `--seed`). The same command must produce the same demo every time so a presenter can rehearse a script and trust that clicking the third row still opens the deal they practised on.

### 3. Idempotent and reversible

Running twice must not double the data; `--reset` must remove **only** generated records and never touch the 7,914 players, world teams, leagues, or valuations. See [Tagging and teardown](#tagging-and-teardown).

### 4. Uses recognisable real names

Arsenal, Chelsea, and Liverpool with real player names and crests are far more convincing than "Demo Club A". The raw material is already there.

## Available raw material

Verified against the database on 2026-08-08.

**Clubs with real budgets** (use these three; the other six are £0 test scratch clubs):

| Club | Owner login | Transfer budget | Wage budget/wk | Squad |
|---|---|---|---|---|
| Arsenal | `arsenal@transferx.com` | £260,000,000 | £50,000,000 | 25 |
| Chelsea | `chelsea@transferx.com` | £200,000,000 | £35,000,000 | 27 |
| Liverpool | `liverpool@transferx.com` | £180,000,000 | £18,000,000 | 31 |

**Agents** (16 active mandates between them):

| Agent | Agency | Login | Active mandates |
|---|---|---|---|
| Marco Rossi | Global Football Agency | `marco.rossi@globalfootball.com` | 5 |
| Sofia Reyes | Premier Talent Group | `sofia.reyes@premiertalent.com` | 5 |
| James Mitchell | Elite Sports Management | `james.mitchell@elitesports.com` | 6 |

**Platform staff:** `admin@club.com` (superuser) — required for `PAPERWORK → CONFIRMED`, which is staff-only.

All existing dev accounts share the password `password123`. Note the caveat in [`SESSION_HANDOVER.md`](../SESSION_HANDOVER.md) — this is local dev data only.

**Ignore these six clubs** — they have £0 budgets and exist as test residue: `Dev Club`, `outsider-tra81`, `Rival Bidders FC`, `Role Demo Rivals`, `Role Demo United`, `Valuation Demo FC`. (`Dev Club`'s owner `dev@transferx.local` also cannot log in at all — Pydantic's `EmailStr` rejects the `.local` TLD.)

## How stage targeting actually works

**The starting stage of a deal is not chosen — it is a consequence of whether the player has an active mandate.**

`offers/service.py::maybe_invite_agent_for_deal` runs immediately after deal creation. It looks for an `ACTIVE` `Mandate` on the player, preferring exclusive and most recent:

- **Mandate found** → sets `deal.stage = AGENT_NEGOTIATION`, creates an `AgentDealInvitation`, notifies the agent.
- **No mandate** → the deal stays at `AGREEMENT`.

So the generator controls the entry point purely by **which player it picks**. To land a deal at `AGREEMENT`, choose a player with no active mandate; to land at `AGENT_NEGOTIATION`, choose one of the 16 mandated players. Everything past that is driven by advancing.

> Implementation note: `advance_deal`'s docstring refers to this function as `_maybe_invite_agent`, which does not exist — the real name is `maybe_invite_agent_for_deal` and it lives in `offers/service.py`, not the deals module. Worth correcting while you're in there.

## Stage preconditions reference

Verified against `backend/app/deals/service.py::advance_deal`. Each row is what must be true *before* the advance call succeeds.

| Target stage | Precondition | Actor allowed |
|---|---|---|
| `AGREEMENT` | Deal created from a player with **no** active mandate | — (entry state) |
| `AGENT_NEGOTIATION` | Deal created from a player **with** an active mandate | — (entry state) |
| `PERSONAL_TERMS` (from `AGREEMENT`) | none | club or staff |
| `PERSONAL_TERMS` (from `AGENT_NEGOTIATION`) | `AgentNegotiation` row exists **and** `club_agreement == AGREED` | mandated agent, club, or staff |
| `PAPERWORK` | `PersonalTerms` row exists **and** `player_consent == AGREED` | club or staff |
| `CONFIRMED` | No `MedicalCheck` with status `FAILED` | **staff only** |
| `COMPLETED` | Deal at `CONFIRMED` | club or staff |

Two side effects worth knowing, because they shape the demo:

- Advancing out of `AGENT_NEGOTIATION` copies commission onto the deal and creates a `PENDING` `AgentCommission` — so the commission panel is only populated on deals that passed through a mandated path.
- Advancing into `CONFIRMED` also flips `status` to `PENDING_COMPLETION` and stamps an `sla_deadline`. A deal sitting at `CONFIRMED` therefore displays an SLA countdown, which demos well.

## Scenario catalogue

Twelve scenarios. Every lifecycle stage gets at least one live instance, and each stage's supporting panels are populated rather than empty.

### Deal-stage scenarios

| ID | Stage shown | Seller → Buyer | Player selection | Agent | Notes |
|---|---|---|---|---|---|
| `D1` | `AGREEMENT` | Liverpool → Arsenal | **unmandated** | — | Terms still editable; shows the deal room at its earliest point |
| `D2` | `AGENT_NEGOTIATION` | Chelsea → Arsenal | **mandated** | Marco Rossi | Leave `club_agreement` at `PENDING` so the negotiation is visibly *live* and the agent has an action to take on camera |
| `D3` | `PERSONAL_TERMS` | Arsenal → Chelsea | **mandated** | Sofia Reyes | Personal terms proposed, `player_consent` left `PENDING` — the consent button is the demo's most compelling single click |
| `D4` | `PAPERWORK` | Liverpool → Chelsea | **mandated** | James Mitchell | Consent given; add a `PASSED` `MedicalCheck` so that panel isn't empty |
| `D5` | `CONFIRMED` | Chelsea → Liverpool | unmandated | — | Shows the SLA countdown and the *Execute Transfer* button |
| `D6` | `COLLAPSED` | Arsenal → Liverpool | unmandated | — | Collapse from `PERSONAL_TERMS` with a declined consent, so the timeline explains *why* |

`COMPLETED` needs no new scenario — three completed deals already exist and render correctly.

### Live market scenarios

All 14 existing offers are terminal, so nothing in the market is currently *live*.

| ID | Shows | Detail |
|---|---|---|
| `M1` | Competitive auction | Liverpool lists a player; Arsenal and Chelsea place **3–4 escalating bids**. Set a reserve price so the seller-only reserve/best-bid confidentiality is demonstrable. Deadline ~3 days out so the countdown is live but won't expire mid-demo. |
| `M2` | Fixed-price listing | Chelsea lists at a stated price, with the fair-value signal visible against it |
| `M3` | Open-to-offers negotiation mid-flight | Arsenal lists; Liverpool offers; Arsenal **counters**; left on Liverpool's turn — demonstrates turn-taking and the counter-offer chain |
| `M4` | Inbound offer awaiting response | A `SENT` offer sitting in Chelsea's inbox, unanswered |

### Supporting-surface scenarios

| ID | Shows | Detail |
|---|---|---|
| `S1` | Spending approval queue | Give Arsenal an `approval_threshold`, add a `MANAGER` staff user, and have them attempt a bid above it so a `PendingApproval` is waiting for the owner. Demonstrates the Phase 5 approvals feature, which currently has no live instance. |
| `S2` | Staff roles | One staff user per role on Arsenal (`SPORTING_DIRECTOR`, `MANAGER`, `SCOUT`, `READONLY`) so the capability matrix — the strongest part of the system — can be demonstrated by logging in as each |

## Command-line interface

Follow the conventions already established by `scripts/create_user.py` (module docstring with both Docker and local invocations, `argparse`, `asyncio`, `sys.path` insert, `async_sessionmaker` from `settings.database_url`).

```
docker compose exec api python scripts/seed_demo.py [options]

  --reset            Remove all generated demo data, then exit
  --refresh          Equivalent to --reset followed by a normal run
  --only ID[,ID...]  Generate only the named scenarios (e.g. --only D2,D3,M1)
  --seed N           RNG seed (default: 20260808) for reproducible selection
  --dry-run          Print the plan — chosen players, clubs, fees — without writing
  --verbose          Log every service call as it happens
```

`--dry-run` matters more than it looks: player selection depends on live mandate and contract state, so being able to preview *which* players a run will pick — before it writes anything — is what makes the script safe to run shortly before a demo.

## Tagging and teardown

Every generated record must be identifiable so `--reset` can remove it without touching real data.

**Recommended approach:** a dedicated marker table, `demo_seed_records (id, entity_type, entity_id, created_at, run_id)`, written to as each entity is created. Teardown reads it and deletes in reverse dependency order.

Rejected alternative — tagging by a magic string in a `notes` field — because notes are user-visible (they'd show up in the demo itself), several relevant entities have no notes column, and a partial failure leaves untagged orphans.

Teardown must delete in dependency order: audit events → commissions → negotiations/invitations → personal terms → medical checks → instalments/clauses → deals → bids/offers/offer events → sales → pending approvals → staff invitations/staff rows → notifications, **then release any budget the generated activity reserved or committed** (see below).

**Teardown must never delete:** players, contracts it did not create, clubs, users that pre-existed the run, world teams, leagues, valuations, or player stats.

## Budget safety

Generated activity moves real money through `ClubFinance`. Bids reserve; accepted deals commit; completion converts committed to spent.

Constraints:

- Keep the **total** reserved + committed per club under ~40% of that club's transfer budget, so a presenter can freely place further bids live without hitting a budget rejection mid-demo. Liverpool is the binding constraint at £180m, and its **wage** budget (£18m/wk) is proportionally much tighter than Arsenal's — size wage figures against it deliberately.
- Derive fees from each player's existing `PlayerValuation` where one exists (2,229 players have one), so asking prices look defensible and the fair-value divergence badge shows a sensible spread rather than nonsense. Vary deliberately: some listings above model, some below, so the signal visibly *does something*.
- `--reset` must release reserved and committed budget rather than orphaning it. A club whose budget drifts down on every reset/reseed cycle will eventually reject bids for no visible reason — an unpleasant thing to discover mid-demo.

## Edge cases and gotchas

**Who consents when the player has no account.** `PERSONAL_TERMS` requires `player_consent == AGREED`, and `deals/router.py::player_consent_to_terms` allows only: the player themselves (if they have a `PlayerProfile`), the mandated agent (**only** if the player has *no* account), or a superuser (`router.py:821`). Almost none of the 7,914 players have accounts, so:

- For **mandated** scenarios (D4), consent via the mandated agent — the realistic path.
- For **unmandated** scenarios (D5), there is no agent and no player account, so **only the superuser can consent**. Use `admin@club.com`.

This is a real constraint, not a workaround: without the superuser path, an unmandated deal whose player has no account cannot legitimately reach `PAPERWORK` at all. Worth flagging separately as a product question — a staff account being able to produce a player's consent record weakens the consent trail that [ADR 0002](../product/decisions/0002-single-capture-point-for-personal-terms.md) exists to protect. Out of scope here; note it, don't fix it.

**Personal terms must be set before consent.** `set_personal_terms` records `pt.agent_id`, and the agent consent path checks the caller against exactly that field. Setting terms as one agent and consenting as another fails.

**Player selection must respect ownership.** `POST /sales` and `accept_offer` validate that the selling club actually owns the player (TRA-138, via `players_service.get_owning_club_id`). Select sellable players from `players.current_club_id`, not arbitrarily from the 7,914.

**Mandated players may not be on the three demo clubs.** The 16 active mandates are not guaranteed to point at players currently contracted to Arsenal, Chelsea, or Liverpool. Resolve this by **querying for the intersection** (mandated ∧ contracted-to-a-demo-club) and, if it's empty, creating a mandate for a suitable squad player rather than silently falling back to an unmandated player — which would quietly produce the wrong stage. Fail loudly instead.

**Transfer windows.** `is_transfer_allowed` returns `True` when no windows are configured, which is the current state — so nothing blocks generation. If a window is ever configured, generation must run inside it.

**Deal-stage deadlocks.** Audit finding H7 notes `AGENT_NEGOTIATION` has no per-stage expiry. `D2` deliberately parks a deal there; that's intended for the demo, but don't be surprised when it never moves on its own.

## Phasing

| Phase | Delivers | Verify by |
|---|---|---|
| **1** | `D1`–`D6` — every deal stage live | Open each deal in the UI; each stage's panel renders with a populated timeline |
| **2** | `M1`–`M4` — live market activity | Market pages show open listings, live bids, and a negotiation awaiting response |
| **3** | `S1`–`S2` — approvals and staff roles | Log in as each staff role; confirm the capability matrix and a waiting approval |
| **4** | `--reset` / `--refresh` round-trip | Reset, verify only generated data is gone and budgets are restored, re-run, confirm identical result |

Phase 1 alone resolves C1. Ship it first rather than holding everything for a complete generator.

## Success criteria

An implementation is done when:

1. Every deal stage — `AGREEMENT`, `AGENT_NEGOTIATION`, `PERSONAL_TERMS`, `PAPERWORK`, `CONFIRMED`, `COMPLETED`, `COLLAPSED` — has at least one deal that opens cleanly in the UI.
2. Every generated deal has a **non-empty audit timeline with attributed actors**. This is the check that proves scenarios were built through the service layer rather than inserted; an empty timeline means the implementation took the shortcut principle 1 forbids.
3. Deals that passed a mandated path show commission terms and a `PENDING` `AgentCommission`.
4. `D3`'s consent button and `D2`'s negotiation are genuinely actionable — clicking through advances the deal correctly.
5. The market shows at least one live auction with competing bids, and one negotiation awaiting a response.
6. `--reset` restores the database to its pre-run state: no generated rows, budgets released, and player/world/valuation data untouched (verify counts before and after: 7,914 players, 2,229 valuations).
7. Re-running after `--reset` with the same `--seed` produces the same scenarios.
8. The full backend test suite still passes (currently 403).

## Relationship to the snapshot

C2 asks for two artifacts. They are complementary and should not be conflated:

| Artifact | Protects against | Rebuild cost without it |
|---|---|---|
| **`pg_dump` snapshot** (committed) | Losing the 7,914 players, leagues, world teams, and valuations — e.g. via `docker compose down -v` | Internet + valid API-Football key + ~595 API requests |
| **`seed_demo.py`** (this spec) | Having nothing to *demonstrate* on top of that data | Hours of manual UI clicking, non-repeatable |

Recommended order: take the snapshot **first** (it is small, immediate, and protects irreplaceable data), then build the generator to layer on top of any restored snapshot. The generator should assume reference data exists and fail with a clear message if it doesn't, rather than trying to fetch it.

## Implementation status

**Phase 1 implemented 2026-08-08** — `backend/scripts/seed_demo.py`. Phases 2–4 of the market/supporting scenarios remain open; `--reset`/`--refresh` (nominally Phase 4) were built alongside Phase 1 because they were needed to iterate safely.

All eight success criteria verified: every stage live with a populated, actor-attributed audit timeline; commissions on mandated paths; reset restores the exact pre-run state (players 7,914 and valuations 2,229 unchanged, deals/sales/offers back to 4/3/14, budgets released); same seed reproduces the same scenarios; backend suite still 403 passing.

**Reverting a completed transfer is also verified.** `--reset` originally handled only `IN_PROGRESS`/`PENDING_COMPLETION` deals, so a deal executed during a demo — the most likely demo action, since `D5` sits one click from it — left the player at their new club and the fee permanently in `transfer_spent`. Now covered end to end: seed → execute `D5` via `POST /deals/{id}/advance` → reset returns squads to 25/27/31, contracts to 3, Chelsea's budget to £200m, Liverpool's spent to £60m, and the player to Chelsea as `CONTRACTED`. The reversal mirrors `_complete_deal`; **keep the two in step if completion's finance logic changes.**

The `pg_dump` half of C2 is also done: `backend/seeds/transferx_reference_20260808.dump` (7.2 MB, 85 tables, round-trip verified).

### Deviations from spec

- **Marker table is created by the script, not an Alembic migration.** `CREATE TABLE IF NOT EXISTS demo_seed_records` runs at startup. Demo tooling should not add a table to the production schema or the migration chain, which stays clean at `0059`.
- **An explicit model/service import block was required.** SQLAlchemy resolves `relationship()` targets by name against the mapper registry, so every model module must be imported before the first query (the same reason `migrations/env.py` carries its own import list). Separately, `app.clubs.service` must be imported explicitly — see below.
- **Phase 1 scope only.** `M1`–`M4` (live market) and `S1`–`S2` (approvals, staff roles) are not built.

### Discovered during implementation

Facts that cost real debugging time and are worth knowing before touching this code:

- **`commission_pct` is a fraction, not a percentage.** It is `Numeric(5, 4)` and `upsert_negotiation_terms` derives the amount as `pct * agreed_fee` directly. Passing `5` for "5%" bills **500%** of the fee — it produced a £66m commission on a £13.2m deal before being caught. Use `0.05`.
- **The `commissionpayer` enum is `BUYER` / `SELLER` / `PLAYER`** — not `BUYING_CLUB`, despite `commission_payer` reading like a club reference elsewhere.
- **`deals`/`offers`/`sales` services depend on someone else importing `app.clubs.service`.** They do `from app import clubs as clubs_module` and then reach for `clubs_module.service.*` at call time. In the running app the routers import it; any standalone script must do so itself or fail with `module 'app.clubs' has no attribute 'service'`.
- **Deal-creation audit events are not actor-attributed.** `accept_offer` takes no `actor_user_id`, so the `DEAL_CREATED` event has a null actor. This is a narrow counter-example to [`permissions-model.md`](../security-and-compliance/permissions-model.md)'s claim that every deal-mutating action is actor-attributed — worth reconciling, but out of scope here.
- **Squads are held on `Player.current_club_id` with almost no contract rows behind them.** Chelsea has 25 squad players and **zero** contracts; Arsenal 23 players / 1 contract; Liverpool 30 / 2. `players_service.normalize_player_status` derives `current_club_id` *from active contracts*, so calling it on a typical player in this database silently converts them to a `FREE_AGENT` with no club. It cost six players their club affiliation during development before being caught and repaired. Anything that calls `normalize_player_status` outside a genuine contract change is dangerous against this data — which is why `--reset` restores the recorded snapshot verbatim instead of recomputing. Worth deciding whether the contract-less squad data is the bug, or whether `normalize_player_status` needs a guard.
- **A pre-existing `COMPLETED` deal still holds committed budget.** Liverpool's W. Fofana deal (`COMPLETED`) retains £15,000,001 in `transfer_committed` that never converted to spent. Predates this work and survives `--reset`; flagged rather than fixed.
- **`advance_deal`'s docstring names `_maybe_invite_agent`, which does not exist.** The real function is `offers/service.py::maybe_invite_agent_for_deal`.

## Related documents

- [`../DEMO_READINESS_AUDIT.md`](../DEMO_READINESS_AUDIT.md) — findings C1 and C2, which this spec closes
- [`../product/workflows/transfer-lifecycle.md`](../product/workflows/transfer-lifecycle.md) — the lifecycle these scenarios instantiate
- [`../architecture/authentication-and-permissions.md`](../architecture/authentication-and-permissions.md) — the capability matrix scenario `S2` demonstrates
- [`../product/decisions/0002-single-capture-point-for-personal-terms.md`](../product/decisions/0002-single-capture-point-for-personal-terms.md) — the consent rule behind the `PERSONAL_TERMS` gotcha
- [`README.md`](./README.md) — spec lifecycle and how this becomes `Implemented`
