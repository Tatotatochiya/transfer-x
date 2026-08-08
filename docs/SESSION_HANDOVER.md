---
title: "Session Handover"
last_updated: 2026-08-08
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

**Session date:** 2026-08-08

**Completed work:**
- Reviewed the full `docs/` tree at session start per the standard reading order (`PRODUCT_SPEC.md` → this file → relevant detail docs).
- Got the local stack running and diagnosed a real login failure: not a Postgres password problem (ruled out directly — connected with `.env`'s credentials, no auth errors in either container's logs), but no seeded account's plaintext password was known. Created `dev@transferx.local` via the bootstrap CLI, then — at explicit request — reset **all 19 users'** passwords to `password123` via a one-off script (bcrypt, via the app's own `hash_password`, then deleted). This is local dev data only; no production environment exists.
- Diagnosed and fixed a real LAN-access bug already sitting uncommitted in the working tree: a built frontend bundle sent every API call to its own origin instead of the backend. Root cause: Docker's `ARG VITE_API_BASE_URL` resolves to `""` when no build-arg is passed (not `undefined`), and `frontend/src/lib/api.ts` used `??`, which doesn't treat `""` as unset. Fixed with `||`; rebuilt and confirmed the fallback compiled correctly into the bundle.
- Discovered `dev@transferx.local` can never actually log in — Pydantic's `EmailStr` validator rejects `.local` as a reserved TLD, at the request-validation layer, same on the API as the website. Use `admin@club.com` (or any other pre-existing/real-TLD account) instead; password is `password123` like everyone else post-reset.
- Diagnosed and fixed vendor player-stats sync (API-Football) being completely broken: every sync attempt crashed on a naive/aware datetime mismatch (`stats/service.py`) writing `vendor_sync_states`. Fixed; verified live with a real login → sync → DB round trip.
- Built per-run vendor sync history: new `vendor_sync_runs` table (migration `0059`), `GET /vendor/runs`, and a "Recent Syncs" section on `AdminVendorPage` with a per-run expandable breakdown (params/result/error/who/timing). All four vendor operations (`sync_league`/`sync_team`/`sync_player`/`compute_form`) now record a run; `compute_form` previously had no error handling at all.
- Synced real data for all 11 leagues tracked in `world_leagues` (season 2025 — the current season): 595 API requests (well under the Pro plan's 7,500/day), ~149 new players, ~12,000 stat snapshots, then recomputed form scores (7,913 players).
- User caught a sharp, real concern — does vendor sync move TransferX-transferred players back to their old real-world team? Verified via code (not assumption): `current_club_id`/`Contract` was never touched by any sync path, and the frontend already prioritizes it everywhere club affiliation is displayed. But found and fixed a real, related latent bug: `team_name` (vendor-sourced display field) was unconditionally overwritten even for players under an active TransferX contract — harmless for display today, but silently wrong stored data that would resurface once a contract lapsed. Verified the fix against a real player already in exactly that state. Wrote up the underlying principle as [ADR 0001](./architecture/decisions/0001-vendor-data-never-overrides-transferx-contract.md) (first architecture ADR in this repo — the folder was previously empty).
- Committed everything as **4 commits split by concern**: `f647389` (LAN access), `abe4360` (timezone fix), `944f4ba` (sync history feature), `4a4775a` (team_name guard). `backend/app/stats/service.py` had two of these concerns mixed in one file — split by temporarily writing a timezone-fix-only version, committing, then restoring the full version for the tracking-feature commit; verified via `git diff` at each step.
- Docs sync (this pass): `CHANGELOG.md`, `IMPLEMENTATION_STATUS.md`, `PRODUCT_SPEC.md` (migration count), `engineering/database-migrations.md` (migration count), `architecture/backend-architecture.md` (vendor module now notes manual-only sync; also found and added **two previously-undocumented background jobs** — `expire_mandates`, `deal_sla` — while re-verifying the job list against `main.py` directly), `architecture/data-model.md` (added the `stats` module's entities, never previously listed), plus the new ADR and its index entry.

**Important decisions:**
- [ADR 0001](./architecture/decisions/0001-vendor-data-never-overrides-transferx-contract.md): vendor-sourced fields must never be written for a player currently under an active TransferX contract — `current_club_id` is always authoritative, full stop. Applies to any future vendor-derived field, not just `team_name`.
- Restarting the `api` container (not relying on `uvicorn --reload`) is necessary after every backend code change in this environment — Docker bind-mount file-watching doesn't reliably pick up edits on Windows. Several verification steps this session were initially confused by this before it was identified.
- Chose to sync only the 11 leagues already present in `world_leagues` for "sync everything," rather than guessing at a broader list — there's no existing "all leagues" concept in the codebase to draw from.

**Outstanding work:**
- **No automated test coverage added** for any of this session's three bug fixes or the new tracking feature — all verification was live/manual (real API calls, real DB queries, a real before/after check against a live contracted player). This is the most concrete gap left behind; see Recommended next task.
- `architecture/backend-architecture.md`'s two newly-added `expire_mandates`/`deal_sla` job rows have unverified exact behavior (marked as an explicit TODO in that doc) — only their existence, interval, and id were confirmed via grep, not what their job bodies actually do.
- Linear access was available briefly at the start of this session (confirmed TRA-143/144/146 are the remaining open Marketplace Core Phase 4 items, all still Backlog) but the MCP connection dropped mid-session and never came back — didn't reconnect to check current state or file/update anything. None of this session's three bug fixes have Linear tickets at all (found live, not pre-ticketed) — worth deciding whether to retroactively file them.
- Everything carried over from the 2026-07-10 session's outstanding list is still untouched and still open: 23 pre-existing frontend test failures, the injury-availability spec's migration re-chain, the `/register` link vs. login-only-page discrepancy, and that session's suggested Linear reconciliation for TRA-151/146/152/86.

**Risks:**
- Every local dev user's password is now literally `password123`, including pre-existing seeded accounts. Fine for this local dev database; flag loudly before this database or any dump of it is ever reused anywhere less throwaway.
- The three vendor-sync bug fixes have zero regression-test coverage — a future refactor of `stats/service.py` or `vendor/sync.py` could silently reintroduce either the timezone crash or the `team_name` overwrite with nothing to catch it.
- Linear may have drifted from the TRA-143/144/146 state this session observed early on, since access was lost partway through and never re-verified.

**Recommended next task:**
- Add regression tests for the three vendor-sync fixes — the timezone fix, the `team_name` contract guard (ADR 0001), and ideally the run-history feature's success/failure recording. This is pure follow-up on verified-but-untested work, not new scope.
- Decide whether to retroactively file Linear tickets for this session's fixes, and reconnect Linear to check whether TRA-143/144/146 have moved since the early-session check.

## Related documents

- [`PRODUCT_SPEC.md`](./PRODUCT_SPEC.md) — read this first, then this file
- [`CHANGELOG.md`](./CHANGELOG.md) — full change history
- [`IMPLEMENTATION_STATUS.md`](./IMPLEMENTATION_STATUS.md) — current verified build status
