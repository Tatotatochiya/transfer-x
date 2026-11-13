---
title: "Session Handover"
last_updated: 2026-11-11
status: Active
owner: "TODO — assign a Documentation Owner"
---

# Session Handover

## Purpose

The single, current handover note between one working session and the next, human or Claude. Read it at the start of every session, right after [`PRODUCT_SPEC.md`](./PRODUCT_SPEC.md).

## Scope

In scope: the latest session's summary, what's in motion now.
Out of scope: history ([`CHANGELOG.md`](./CHANGELOG.md)). This file is overwritten, not appended to.

## How this file works

Overwritten at the end of each session by the [`session-lifecycle`](../.claude/skills/session-lifecycle/SKILL.md) skill. It holds exactly one thing: the latest summary.

## Latest Session Summary

## Session Summary — 2026-11-13 (valuation `market-v3`: review, made safe to ship)

**Completed work:**
- Reviewed the uncommitted `valuation-v3-fee-anchor` work against [`docs/feature_spec/valuation/execution-plan.md`](./feature_spec/valuation/execution-plan.md) and [`docs/feature_spec/valuation/execution-log.md`](./feature_spec/valuation/execution-log.md) (Round 3 there has the detail). The engine, last-fee lookup, admin endpoints, sync fix and tests match the plan.
- Brought the branch up to `origin/main` (`15e6ba1`: type and colour, move reminders). Conflicts resolved in `FactsStrip.tsx` and five docs.
- **Migration renumbered `0111` → `0112`** (`0112_manual_transfer_fees.py`, revises `0111`). `main` gained `0111_move_reminders` on 2026-11-12; shipping the old file would have given Alembic two revisions called `0111` and stopped the API at start. `alembic heads` now prints one head, `0112`.
- **The fee anchor ships switched off:** `VALUATION_FEE_ANCHOR_ENABLED` (default `false`). While off, the fee is not loaded into the features and rows are computed, labelled and replayed as `market-v2`. Staff-entered fees, the vendor-sync fix and the fee's provenance are live either way.
- The admin "Transfer fees" card and the popover's "Last fee not used" line moved onto the type roles, so `designSystem.test.ts` passes with an empty allowlist.
- Valuation docs moved into [`feature_spec/valuation/`](./feature_spec/valuation/README.md) (model, signal, market data, sample report, brief, execution plan and log) with an index; `.gitignore` covers `*.env`.
- Tests: backend 997 passed and 7 failed on Windows, all seven the `strftime("%-d")` error in untouched code (`app/reminders/service.py`, `app/players/real_world.py`), which is valid on Linux; frontend 490 passed; `tsc -b` clean.

**Important decisions:**
- The production backtest and outcome report are still not run: the env file supplied holds only the local Docker database (`db:5432`), and this machine has no Docker. Because the plan makes that run a blocking gate, the anchor is off by default instead of live and unproven.
- The migration-first route (plan Addendum 2) is dropped: the migration now ships with the code in one PR. The local branch `migration-0111-manual-transfer-fees` and its worktree are stale and can be deleted.

**Outstanding work:**
- Merge the pull request from `valuation-v3-fee-anchor`. `conversation.jfif` and `docs/presentations/` are left untracked.
- After deploy (migration `0112` applied): run, read-only against production, `scripts.valuation_backtest --csv`, `--grid` and `scripts.valuation_outcome_report`; fill the `TODO` table in [`valuation/model.md`](./feature_spec/valuation/model.md); show the product owner and ask the plan's three section-11.5 questions.
- Only then set `VALUATION_FEE_ANCHOR_ENABLED=true` on `backend` and `stats-worker` ([deployment](./operations/environments-and-deployment.md#the-last-fee-anchor-switch)).
- Follow-up: PlayerElo pilot in admin-only shadow mode.

**Risks:**
- The `stats-worker` runs the new image without migrating. Merge away from the 17:00 and 22:00 UK refreshes so the API has applied `0112` before the worker next reads `player_transfers`.
- A staff-entered fee changes the comparables index (it replaces the vendor's figure for the same move; release clauses are left out), so it can move other players' market-rate step at the next recompute. Intended, and audited.
- `source_note` is public to clubs and to signed-out viewers of a public player; the form says so.
- Pre-existing: seven Windows-only `strftime("%-d")` test failures (six in `test_move_reminders.py`, one in `test_real_world.py`); the suite was not run on Linux in this session.

**Recommended next task:**
- Commit, open the PR, merge between refreshes, then run the read-only production backtest and outcome report.

## Session Summary — 2026-11-12 (move reminders)

**Completed work:**
- Built [`move-reminders`](./feature_spec/move-reminders/README.md) on branch `move-reminders`, on top of `type-and-colour` (PR #70): `app/reminders/` (who holds the move, cooldowns, escalation, sending, automatic job), migration `0111`, notification types `MOVE_REMINDER` / `MOVE_ESCALATED` (your-move push tier, emailed), `MoveReminder` on the deal and offer status cards, the enquiry page and Lite's sent page.
- Checked on the running stack: Chelsea reminded Man City about the £30M D. Mukasa offer; notification and Mailpit email arrived.
- Tests: backend 951 passed, frontend 484 passed, `tsc -b` clean.

**Important decisions:**
- Covers offers, deals and enquiries; the server decides who holds the move. 24 hours before a reminder, 48 between (2 and 12 on deadline days); escalation after two ignored reminders or 7 days; automatic at 3 and 7 days, skipping anything idle over 30 days. Confirmed deals stay with the existing completion SLA.

**Outstanding work:**
- Push `move-reminders` and open its PR (after PR #70, which it builds on).
- The hourly job will send automatic reminders on the local and production data once deployed: anything idle 3–30 days gets one. Worth a look at production's open offers and deals before shipping.
- The reminder email carries the sentence but not the note.

**Risks:**
- First deploy sends a batch of automatic reminders and emails at once (bounded by the 30-day rule).

**Recommended next task:**
- Merge PR #70, then the move-reminders PR; then the registration checklist.

## Session Summary — 2026-11-11 (type and colour)

**Completed work:**
- Built [`type-and-colour`](./feature_spec/type-and-colour/README.md) on branch `type-and-colour` (15 commits, not yet pushed): type roles and colour tokens in `index.css`; shared components; colour meanings (AI violet, neutral categories, blue only for tappable, `primary-success` removed, `text-on-accent`); one compact money format; the sweep of every area including Lite and admin; blue dark-mode accent; a second pass so Caption is only for labels.
- `frontend/src/test/designSystem.test.ts`: banned classes with a ratchet allowlist (now empty) and contrast pairs in both themes. `npm run check:design`.
- Measured with `measure-type.mjs`'s `measure()` over CDP: 0% under 13px and ≤ 6 sizes on every measured route at 390 and 1280.
- Docs: TOKENS.md (typography, colour roles, money), RESPONSIVE.md, SCREENS.md note, CHANGELOG, feature_spec index, IMPLEMENTATION_STATUS.
- `STARTER.md` (new, repo root): fresh clone to running app with the reference snapshot, Premier League clubs and demo deals; `.env.example` rewritten to cover every setting. README, getting-started, docs home, PRODUCT_SPEC, RULES, coding standards, testing strategy, frontend architecture and database migrations brought up to date.
- Checked on a scratch database (`tx_starter_check`, dropped afterwards): restore, `alembic upgrade head`, onboarding, demo seed and account scripts. That found two bugs, both fixed: migration `0062` collided with the snapshot's `vendor_sync_runs`, and `seed_demo.py` was missing model imports.
- Tests: backend 938 passed, frontend 480 passed (65 files), `tsc -b` clean.

**Important decisions:**
- Q1 default taken: dark accent is blue with dark text on it. Q2: admin swept in the same PR.
- Caption (13px) is for labels, badges, counts and timestamps; sentences and meta lines are Small (14). Deviations are listed in the spec's §15.

**Outstanding work:**
- Push `type-and-colour` and open the PR (waiting for the user's go-ahead). It also carries `STARTER.md` and the two setup fixes.
- `STARTER.md` hasn't been followed on a truly fresh clone (a new machine or `docker compose down -v`); the steps were checked on a scratch database beside the existing one.
- The reference snapshot is from 2026-08-08: new demo accounts and data since then come only from the scripts. A fresh snapshot would shorten the starter.
- Not checked: the Deal room (no local deal with a signed-in party), 768px, 200% zoom, a real iPhone, Lite offer card.
- Most text is 14px rather than 15px on Dashboard, Player, Offer, Account and Make an offer.
- Production: one club's weekly wage budget of about £50M needs a staff correction (carried over).

**Risks:**
- Large visual change across every page: wraps or clipping in tight rows that the by-hand pass didn't reach. Positions lost their colours (fallback in the spec's §13).
- Dark-mode users see the accent change from green to blue.

**Recommended next task:**
- Review and merge the type-and-colour PR, check the Deal room and Lite offer card by hand, then the registration checklist.

## Related documents

- [`PRODUCT_SPEC.md`](./PRODUCT_SPEC.md): read first
- [`IMPLEMENTATION_STATUS.md`](./IMPLEMENTATION_STATUS.md): verified state and gaps
- [`CHANGELOG.md`](./CHANGELOG.md): history
