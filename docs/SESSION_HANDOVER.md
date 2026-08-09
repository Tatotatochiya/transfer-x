---
title: "Session Handover"
last_updated: 2026-08-09
status: Active
owner: "TODO — assign a Documentation Owner"
---

# Session Handover

## Purpose

The single, current handover note between one working session and the next — human or Claude. Read this at the start of every session, right after [`PRODUCT_SPEC.md`](./PRODUCT_SPEC.md).

## Scope

In scope: the most recent session's summary — what's in motion right now.
Out of scope: full project history (see [`CHANGELOG.md`](./CHANGELOG.md)); this file is not a log.

## How this file works

This file is **overwritten**, not appended to, at the end of each session — maintained by the [`session-lifecycle`](../.claude/skills/session-lifecycle/SKILL.md) skill. It should always contain exactly one thing: the latest session's summary. If you want history, `CHANGELOG.md` has it; this file only needs to answer "what does the next session need to know right now."

## Latest Session Summary

**Session date:** 2026-08-09

**Completed work:**
- Read the full `docs/` tree at session start per the standard reading order. Committed the previous session's pending docs (vendors-sync session handover and ADR 0001) as `89a6d93`.
- Produced a **merged demo-readiness audit** consolidating two independent reviews. Every retained finding verified against the running system; six unverified claims from the other review are recorded in a Corrections section rather than silently dropped. 22 findings: 4 critical, 7 high, 11 medium — separated by demo blockers vs. pilot blockers for the two different audiences. Committed as `222694b` ([`docs/DEMO_READINESS_AUDIT.md`](./DEMO_READINESS_AUDIT.md)).
- **Closed C2 — committed a reference database snapshot** (`backend/seeds/transferx_reference_20260808.dump`, 7.2 MB, 85 tables, round-trip verified) after the first attempt was silently corrupted by a Windows shell redirect. Committed as `2d9aedb`.
- **Closed C1 — built the demo scenario generator** (`backend/scripts/seed_demo.py`, 746 lines) with every deal stage live. Wrote the full implementation spec at [`feature_spec/demo-scenario-generator.md`](./feature_spec/demo-scenario-generator.md). Six scenarios (AGREEMENT through COLLAPSED) using Ødegaard, Saka, Caicedo, Gravenberch etc. from the three real clubs. Built through the real service layer — every deal has a populated, actor-attributed audit timeline and real commission and budget records. `--reset` restores the exact pre-run state including fully reversing a transfer executed mid-demo (player back at their club, budgets restored). Deterministic by seed. Spec and script committed as `28d25ac`. Success criteria verified: all eight, including the completed-transfer round-trip, with backend suite at 403 passing.
- **Closed C4 — fixed the scheduler so 24h jobs actually fire.** APScheduler interval jobs with no `next_run_time` schedule their first run at `now + interval`, so 24h jobs never ran (never in dev, unreliably in prod). Evidence: valuations sat at 2026-07-06 for over a month. Added `next_run_time` to all nine jobs, staggered 3s–15s. After restart: HIGH confidence rows went from 0 to 948 (40.2%), MEDIUM 814, LOW 597 — the 12k vendor-sync stat snapshots finally reached the model. Committed as `e728e59`.
- Docs sync at session end: `CHANGELOG.md` and `IMPLEMENTATION_STATUS.md` brought current for all four audit items above. Committed as `693b250`.

**Important decisions:**
- **Scenario generator drives the real service layer, never does INSERT.** A hand-inserted deal renders with an empty timeline — exactly the "never done a transfer" impression the script exists to fix. Success criterion #2 (every deal has a populated audit timeline with attributed actors) is the proof.
- **Marker table created by script, not an Alembic migration.** Demo tooling should not add a table to the production schema or the migration chain — it stays clean at `0059`.
- **`--reset` writes back a player snapshot, never calls `normalize_player_status`.** This database assigns squads through `Player.current_club_id` with almost no contract rows (Chelsea: 25 players, 0 contracts). `normalize_player_status` derives club from active contracts, so calling it silently turns those players into free agents. This was discovered the hard way — it cost six players their club affiliation during development before being caught and repaired.
- **Scheduler fix: every 24h/6h job now fires on restart.** The previous behaviour made the entire scheduled-job layer effectively dead unless the process survived a full interval without restart — which never happens in dev and is unreliable in production.

**Outstanding work:**
- **Phase 2–3 of the demo generator** (market scenarios M1–M4: live auctions, fixed-price listings, counter-offer negotiation, inbound offers; supporting scenarios S1–S2: spending approvals queue, one staff user per role on Arsenal). Spec is written, script has the framework. All 14 existing offers are still terminal — nothing in the market is live.
- **Audit items C3, H1, H2, H3 not yet addressed.** C3 (close self-registration) is trivial and the oldest open decision — it was made but never enforced. H1 (isError on list pages) is scoped but larger. H2 (dead AdminHealthPage links, three string changes). H3 (row locks on offer accept / deal completion / instalments). See the audit's recommendation table for the full priority order.
- **23 frontend test failures remain — all stale, no product bugs.** Nine files. All four failing files identified (missing CompareProvider wrapper, redesigned UI selectors, one label rename). Also `testing-strategy.md` is still stale (claims 19 backend files / 274 tests; actual 26 / 403).
- **A pre-existing COMPLETED deal holds orphaned committed budget.** Liverpool's W. Fofana deal retains £15,000,001 in `transfer_committed` that never converted to spent. Survives `--reset` — flagged, not fixed.
- **`deal_sla` and `expire_mandates` job bodies are still unverified** — marked as TODO in `backend-architecture.md` since the previous session. Now that the scheduler fix ensures they actually run, the priority of verifying them has gone up.
- Linear MCP was connected at the start of this session (confirmed the existing TRA-143/144 backlog state) but disconnected mid-session. Nothing was created or updated in Linear.

**Risks:**
- **contract-less squad data.** Chelsea has 25 squad players and zero active contracts; Arsenal 23/1; Liverpool 30/2. `normalize_player_status` would free all of them. Any code that touches contracts and then calls the normalizer — exactly as its own docstring instructs — will silently corrupt the squad. Worth deciding whether the data or the normalizer is the bug.
- **`commission_pct` is a fraction, not a percentage.** `Numeric(5,4)`, multiplied straight by the fee. Passing `5` for "5%" bills 500% — it produced a £66m commission on a £13.2m deal in development. Nothing documents this, and the failure is silent if the fee is small enough to fit the column.
- **`commissionpayer` enum is `BUYER` / `SELLER` / `PLAYER`** — not `BUYING_CLUB`, despite `commission_payer` reading like a club reference elsewhere.
- **`app.clubs.service` must be imported explicitly** in any standalone script. `deals/offers/sales` services do `from app import clubs as clubs_module` and reach for `clubs_module.service.*` — which only resolves if a router already loaded it. Any script outside the request cycle hits `module 'app.clubs' has no attribute 'service'`.
- **deal-creation audit events are not actor-attributed.** `accept_offer` takes no `actor_user_id`, so the `DEAL_CREATED` audit event has a null actor. A narrow counter-example to `permissions-model.md`'s otherwise-accurate claim. The six demo deals inherit this — only stage-advance events carry actors.
- **Windows is a second-class environment** for this tooling. The initial `pg_dump` was silently corrupted by a shell redirect (fixed by dumping inside the container and `docker cp`), and Docker bind-mount file-watching doesn't reliably pick up edits (restart `api` after every backend change).
- **Every dev user's password is still `password123`**, and the committed snapshot shares that state. Local dev only; flag before any reuse.

**Recommended next task:**
- **C3 — close self-registration** is the highest-value remaining item: trivial effort, enforces an already-made product decision, removes the worst answer in a client meeting (verified exploit: anyone can claim any player's identity via `POST /auth/register` and gain binding personal-terms consent rights). Three changes: remove the route, the endpoint paths, and the "Create an account" link.

**Secondary tasks worth doing in the same session:**
- H2 (dead AdminHealthPage links, 3 strings) and M2 (remove "Rumors coming soon" card) — both trivial.
- H3 (row locks on offer accept / deal completion / instalment payment) — small, strong signal to a club evaluator.
- Phase 2 of the generator (live market activity) — all 14 current offers are terminal; the direct counter-offer negotiation and live auction UX can't be shown.

## Related documents

- [`PRODUCT_SPEC.md`](./PRODUCT_SPEC.md) — read this first, then this file
- [`CHANGELOG.md`](./CHANGELOG.md) — full change history
- [`IMPLEMENTATION_STATUS.md`](./IMPLEMENTATION_STATUS.md) — current verified build status
