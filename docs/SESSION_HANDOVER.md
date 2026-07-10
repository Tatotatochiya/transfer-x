---
title: "Session Handover"
last_updated: 2026-07-10
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

**Session date:** 2026-07-09 – 2026-07-10

**Completed work:**
- **Implemented Club Team Accounts, Roles & Onboarding end to end — all six phases** of [`feature_spec/club-team-roles-and-onboarding.md`](./feature_spec/club-team-roles-and-onboarding.md) (spec now `status: Implemented` with a 9-point "Deviations from spec" section):
  - **P1 — capability enforcement (TRA-151):** `app/clubs/capabilities.py` (enum + matrix + `require_club_capability` / `ensure_club_capability` / `ensure_capability_if_club_member`), `StaffRole` gains `SPORTING_DIRECTOR`/`SCOUT` (migration `0049`), `require_club_write_access` deleted and every club write route gated — including gaps the re-grep found (offer messages, squad edits, player/contract creation). `GET /clubs/me/membership` + frontend `useClubCapabilities` hook; buttons hide by capability; sidebar shows "Staff: <Role>".
  - **P2 — staff deal access (TRA-146):** `is_deal_participant` + deal-router club resolution now owner-or-staff; audit log/CSV, medical-check and personal-terms GETs verified to route through it; staff comments labeled with the club name. D4 regression test in place.
  - **P3 — notification routing (TRA-152):** `club_recipient_user_ids` / `notify_club` (D5 mapping) replaced every club→bare-owner notification site; WS pushes go to all club members via `club_member_user_ids`.
  - **P4 — team management + invitations (TRA-86):** `ClubStaffInvitation` (sha256 token at rest, 7-day TTL, single-use; migration `0050`), owner endpoints under `/clubs/me/staff`, public preview/accept under `/auth/invitations/{token}`, D10 removal (row deleted + user deactivated), club-scoped audit events, invitation email helper, Team page + `/accept-invite` page.
  - **P5 — approval thresholds (D7):** `approvals` module + `pending_approvals` + `ClubFinance.approval_threshold` (migration `0051`); MANAGER money actions ≥ threshold return 202 and wait; owner/SD decide; execution re-validates fresh (stale → `APPROVED_FAILED` + reason, both notified); requester cancel; daily `approval_expiry` job; Approvals page, Finance-page policy card, 202 handling in bid/offer forms; 3 new NotificationTypes wired through all four frontend touchpoints.
  - **P6 — first-run checklists (D8):** `OnboardingChecklist` on club dashboard / agent pipeline / player profile; done-states purely from existing queries + localStorage visit-flags; dismissal per user id; zero new endpoints.
- **Tests:** 57 new backend tests across `test_capabilities.py` (matrix-driven roles × capabilities, membership contract, D4, staff deal reads, superuser-bypass-first, removed/deactivated staff, notification routing), `test_team_management.py` (invitation lifecycle + token security + 409s + D10), `test_approvals.py` (capture/exemptions/threshold-boundary, scenario-3 walkthrough, APPROVED_FAILED, one-way status machine, expiry, policy gating). **Full backend suite: 362 passed. TypeScript clean. Frontend suite unchanged (same 23 pre-existing failures, 96 passing).**
- Documentation per the spec's definition of done: authentication-and-permissions.md club-roles TODO filled with the matrix + onboarding + approvals; permissions-model.md gained five boundary rows and moved TRA-146 to Resolved; personas.md gained the Club Staff persona; glossary (Club staff role, Invitation, Approval threshold); data-model, backend-architecture (module + jobs), api-reference rows; CHANGELOG entry; IMPLEMENTATION_STATUS row; spec + index statuses.

**Important decisions (recorded in the spec's deviations section):**
- D4 order honoured within one session: gates first, visibility second; pinned by test.
- Deal room uses a member-conditional capability check (blanket dependency would 403 agents/players).
- Approval capture sits after router-level guards; deep validation only at execution (an approval is an intent, not a hold).
- Invitation links are shown exactly once (token never stored) — the Team page says so; `full_name` dropped from accept (no User column).
- WS pushes widened to all club members alongside role-mapped notifications.

**Outstanding work:**
- **Migrations `0049`–`0051` not yet applied to the dev DB** and the spec's demo script not yet driven live — start the stack (`docker compose up -d`; the API entrypoint runs `alembic upgrade head`) and walk the spec's demo script (§ Demo script, phases 1–5). Remember the frontend container needs `docker compose up -d --build frontend` to pick up UI changes (static build, no volume mount).
- Nothing committed to git — all changes are unstaged working-tree edits awaiting review/commit.
- 23 **pre-existing** frontend test failures on `main` (verified again unchanged: `PlayerCard.test.tsx` missing `CompareProvider` wrapper, `PlayerFilters`, `StatsPanel`, `badges dealStageLabel`). Untouched per surgical-changes rule; worth a small cleanup ticket.
- Observed discrepancy (not resolved, out of scope): the login page has a "Create an account" link to `/register` — the standing product decision on record says the login page is login-only with no self-registration UI. Surface for a deliberate decision rather than silently removing either.
- The injury-availability spec remains `Active`/unimplemented, and now needs re-chaining onto migration head `0051` (it assumed `0047`).
- **Suggested Linear reconciliation, not executed** (suggest-only rule): mark/annotate TRA-151, TRA-146 (link the D4 note), TRA-152, TRA-86 as shipped with a link to the spec + deviations; file the two proposed tickets the spec names (approval thresholds; first-run checklists) as shipped-on-arrival or fold them into the same closure; TRA-28's closing comment; plus the previous sessions' still-open suggestions (TRA-91/92 closure, spec links, injury-spec ticket).

**Risks:**
- The approvals execution path replicates counterparty notifications in `approvals/service.py::_execute` (the originals live in routers) — if a router's notification behaviour changes, keep the two in sync or extract them into the service layer.
- Invitation emails no-op silently without `SMTP_HOST` (expected in dev) — the accept URL in the create response is the dev path; don't lose it.

**Recommended next task:**
- Bring the stack up, apply `0049`–`0051`, and walk the spec's demo script end-to-end in the browser (invite scout + manager via copy-link, scout's gated UI, £5m threshold → manager £6m bid → 202 → SD approves, read-only board member's control-free deal room, removal → next click lands on login). Then commit.
- Then the injury-availability spec is the last remaining `Active` spec.

## Related documents

- [`PRODUCT_SPEC.md`](./PRODUCT_SPEC.md) — read this first, then this file
- [`CHANGELOG.md`](./CHANGELOG.md) — full change history
- [`IMPLEMENTATION_STATUS.md`](./IMPLEMENTATION_STATUS.md) — current verified build status
