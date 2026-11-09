---
title: "Session Handover"
last_updated: 2026-11-09
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

## Session Summary — 2026-11-09 (follow-ups)

**Completed work:**
- PRs #65 and #66 merged (Browse Players).
- Branch `follow-ups-nov`, 8 commits, not pushed yet:
  - Deal collapse reason stored and shown (`collapse_reason`, `collapsed_by_club_id`).
  - Admin warning for a weekly wage budget above £5M.
  - Browse Players price filter in pounds (`min_price`/`max_price`, shared `_with_price`).
  - Offer page: the seller's asking price in the gap line (`your_asking_price` on the Lite card).
  - Offer page: "waiting for approval" after a 202 (`pending_approval`), and no duplicate approval requests.
  - Unsent conversation drafts survive the 1024px layout switch.
  - Unread count on Messages: `conversation_reads` (migration `0110`), `unread` on `GET /conversation`, `POST /conversation/read`.
  - 13px/44px pass on the reused message and timeline components.
- Tests: frontend 61 files, 426 passing; backend deals, offers, approvals, conversation, players, Lite and negotiation tests, 199 passing.

**Important decisions:**
- Unread is per person, keyed by player + buying club (one conversation per transfer, ADR 0008); never-opened conversations count only the last 14 days; "read" means up to the newest message seen, by its own timestamp.
- The collapse reason is visible to both clubs (dialog says so).
- The asking price beats the valuation in the seller's gap line; the buyer never sees either.

**Outstanding work:**
- Push `follow-ups-nov` and open its PR; migration `0110` runs on deploy.
- Production: correct the club whose weekly wage budget is about £50M (staff, admin club page).
- Earlier: registration checklist; real-iPhone checks; Railway test-data cleanup.

**Risks:**
- No eslint in the repo, so lint never runs.
- Backend tests run on SQLite, which stores whole seconds; the unread test backdates rows to stay reliable.

**Recommended next task:**
- Registration checklist: split the single "registration" paperwork step into the league's real items.

## Related documents

- [`PRODUCT_SPEC.md`](./PRODUCT_SPEC.md): read first
- [`IMPLEMENTATION_STATUS.md`](./IMPLEMENTATION_STATUS.md): verified state and gaps
- [`CHANGELOG.md`](./CHANGELOG.md): history
