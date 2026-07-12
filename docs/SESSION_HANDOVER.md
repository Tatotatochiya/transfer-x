---
title: "Session Handover"
last_updated: 2026-07-12
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

**Session date:** 2026-07-12

**Completed work:**
- **Administrator platform audit** — a full product audit of the admin portal across all 16 admin sections (dashboard, users, clubs, staff, players, sales, deals, offers, windows, verification, world import, vendor sync, analytics, AI, health), read-only, no code changes during the audit itself. [`docs/audits/2026-07-12-admin-platform-audit.md`](./audits/2026-07-12-admin-platform-audit.md).
- **Remediated the three findings the user selected from that audit** (H1, H2, H3), plus C1/C2 as an unavoidable side effect of H1:
  - **H1 — reason-required confirmation on six destructive admin actions** (force-complete, force-collapse, force-withdraw-offer, cancel-sale, delete-window, remove-staff). Each now requires a non-blank reason, rejected with 400 if missing, and the reason is actually recorded (deal audit log for complete/collapse, offer event payload for force-withdraw, sale event `notes` for cancel, the generic `AuditEvent` table for window-delete/staff-removal — the last two needed no migration since `entity_type` is a free-text column). `staff_complete` never had a reason field at all before this; `collapse_deal`'s existing CONFIRMED+-reason rule used to exempt staff (`not is_staff and ...`) — that exemption is gone, closing the exact "silently waived for the actor with the most power" gap the audit called out. Frontend: `ConfirmContext` gained `confirmWithReason()` (kept separate from the existing `confirm()` so none of its ~10 other call sites needed touching); all six admin action buttons now go through it.
  - **C1/C2 — fixed as a necessary side effect of H1, not separately in scope.** `admin_cancel_sale` assigned `SaleStatus.CANCELLED`, an enum member that has never existed — every call 500'd, so H1's reason capture had nowhere to land on that path. It now delegates to `sales_service.withdraw_sale` (extended with `is_staff`/`reason` params and staff-attributed notification copy instead of always saying "the seller"), the same cleanup path clubs use — releases every bidder's reservation, rejects linked offers, notifies everyone. C3 (offer force-withdraw still doesn't release the buyer's own reservation) and the rest of the audit's bugs/gaps are untouched.
  - **H2 — six-stage deal visibility.** `AGENT_NEGOTIATION`/`PERSONAL_TERMS` deals were dropped from `get_deals_by_stage`'s zero-init, the dashboard pipeline bar, the deals kanban board, and the health-check staleness scan — all four only ever knew about `AGREEMENT`/`PAPERWORK`/`CONFIRMED`. Now all five active stages are covered everywhere, from one shared frontend source of truth (`lib/badges.ts`: `ACTIVE_DEAL_STAGES`, `DEAL_STAGE_STALE_DAYS`, `DEAL_STAGE_COLOR`) instead of three hand-duplicated arrays. Found and fixed in passing: `AdminDealResponse` never returned `updated_at` at all, so the kanban board's "stale" badge was silently always computed from `created_at`.
  - **H3 — all four staff roles in the admin panel.** It only ever offered `MANAGER`/`READONLY` in both create and edit dropdowns — a `SPORTING_DIRECTOR` or `SCOUT` staff member's role rendered wrong and could only be downgraded. Now offers and correctly labels all four, reusing `TeamPage.tsx`'s existing role descriptions (moved to `lib/badges.ts` as `STAFF_ROLE_INFO`/`STAFF_ROLE_ORDER` so the two surfaces can't drift apart).
- **Backend test suite: 437 passed** (grew from 424 — 13 new regression tests covering all of the above, since the audit itself had flagged these exact endpoints as untested). **Frontend:** zero new `tsc` errors introduced (verified by diffing against a pre-change baseline via `git stash`); one pre-existing error fixed as part of H2 (the `updated_at` gap). All pre-existing Vitest failures (23, unrelated `.test.tsx` files) confirmed pre-existing via the same baseline diff.
- **This documentation pass** — `CHANGELOG.md` (new Fixed/Added entries), `security-and-compliance/permissions-model.md` (new confidentiality-boundary row for reason-required staff overrides, new Resolved-gaps entry), and the audit file itself (a `## Remediation status` section added — the findings themselves were left as-written, since this is a point-in-time record, not a living document).

**Important decisions:**
- **Reused the club-side `withdraw_sale` for admin cancellation rather than writing a parallel admin-only cleanup path.** The alternative (duplicating budget-release/offer-rejection logic inside `admin_service`) would have been a second way to do the same thing — exactly what `engineering-standards` says to avoid. `withdraw_sale` gained `is_staff`/`reason` params instead.
- **Staff now faces the same CONFIRMED+-collapse reason bar as clubs, not a stricter one.** Considered requiring a reason for staff-collapse unconditionally (any stage), but that would have been inventing a new rule nobody asked for; matching the existing club-side threshold exactly is the minimal fix for "silently exempt."
- **`staff_complete` requires a reason unconditionally** (not stage-conditional like collapse) — there's no existing club-side equivalent to mirror, and it's the single most consequential admin action in the system (full bypass of medical/window/consent gates per ADR 0001), so an unconditional bar is the more defensible default.
- **C3 and every other audit finding besides H1/H2/H3 were deliberately left open** — the user asked specifically for these three; C1/C2 got fixed only because H1 mechanically required touching the same broken function.

**Outstanding work (from the 2026-07-12 admin platform audit, not yet actioned):**
- **C3 — force-withdrawing an offer still doesn't release the buyer's reserved budget.** `admin_force_withdraw_offer` never calls `_release_offer_budget`; the admin UI now warns about this explicitly in the confirm dialog, but the underlying stranded-reservation bug is unfixed.
- **H4–H7** — hard-delete of staff accounts with no soft-delete/restore; unauthenticated-to-superuser vendor-sync endpoint (`POST /vendor/sync/players/{id}` only requires `get_current_user`); zero audit logging on most admin mutations (H1's fix covers six actions specifically, not the rest of the admin surface — password resets, superuser grants, budget edits, broadcasts, player reassignment are all still untraced); no protection against deactivating the last superuser.
- **M1–M10** — phantom sale-status filter values (partially addressed: `AdminSalesPage`'s dropdown was corrected to the real enum as a mechanical consequence of the C1/C2 fix, but the same audit-wide sweep for other pages wasn't done); missing `crest_url` on admin club creation; misleading delete-user confirmation copy; no session revocation on admin password reset; no window date validation on create; and the rest of the report's medium/low findings and the Top-20 recommendations — see the audit file directly.
- The prior session's outstanding transfer-workflow items (M1/M2/M3/M5/M6 re-audit, medium gaps) are unchanged by this session — see `docs/audits/2026-07-12-transfer-workflow-audit.md` directly, since this session didn't touch that area.
- Unpushed local commits from prior sessions may still be ahead of `origin/main` — verify before assuming this session's commits are the only ones pending push.

**Risks:**
- **`admin_force_withdraw_offer`'s reason is now captured but the underlying budget bug (C3) it's describing is still live** — an admin reading the confirm dialog's warning and proceeding anyway will still strand the buyer's reservation. The warning is honest, not a fix.
- **The generic `AuditEvent` table now has entity types (`TRANSFER_WINDOW`, `CLUB_STAFF`, `OFFER` for force-withdraw) with no dedicated viewer** — the events are recorded correctly (verified via the regression tests) but there's still no admin UI to read them back, so today they're a trail for someone querying the database directly, not yet a feature.
- Same SQLite-vs-Postgres `SELECT ... FOR UPDATE` caveat as before still applies to any locking this session touched (`withdraw_sale`'s row lock) — behavior is tested for correctness, not verified under real concurrency.

**Recommended next task:**
- C3 (offer force-withdraw budget release) is the natural next fix — same shape as the C1/C2 fix this session did (a one-line call to the existing `_release_offer_budget` helper), and it's the one honesty gap the H1 UI copy now explicitly flags to admins.
- After that, H6 (admin audit logging) generalized beyond the six H1 actions would give the `AuditEvent` entity types this session introduced an actual viewer, closing the "trail exists but nobody can read it" gap noted above.

## Related documents

- [`PRODUCT_SPEC.md`](./PRODUCT_SPEC.md) — read this first, then this file
- [`CHANGELOG.md`](./CHANGELOG.md) — full change history
- [`IMPLEMENTATION_STATUS.md`](./IMPLEMENTATION_STATUS.md) — current verified build status
