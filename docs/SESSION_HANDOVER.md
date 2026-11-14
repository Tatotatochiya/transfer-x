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

## Session Summary — 2026-11-13 (demo gaps)

**Completed work:**
- Reviewed demo mode for gaps after a report that agents never came back with personal terms. Found and fixed six on branch `demo-gaps` ([demo mode](./feature_spec/demo-mode.md)):
  1. With an agent, the tester buying, nobody proposed personal terms ("Waiting on the agent" forever). The agent now prepares them and agrees them for the player (`demo/house.py`).
  2. An agent or player whose account had *ever* been used never answered in any demo; now only while someone is signed in as him (`SIGNED_IN`, two hours).
  3. "After a few minutes" waited 3 minutes before each of the house's steps in a row; it now counts from the tester's last move on the deal.
  4. "Make them move now" on demo deals (`POST /demo/deals/{id}/make`, `DemoDealControls` on the deal page).
  5. Reminders in a demo can go at once and the house answers them; automatic reminders skip demo transactions.
  6. House clubs answer enquiries.
- Tests: backend 956 passed, frontend 486 passed, `tsc -b` clean.

**Important decisions:**
- "Signed in" = active in the last two hours: the house may act for a real agent in a demo when he isn't online. Everything it does is journaled and undone by Reset, and only on deals the demo made.
- "Make them move now" on a deal also answers for an agent or player who is signed in (it's the tester's explicit choice); a reminder doesn't.

**Outstanding work:**
- **PR #71 was merged before its last two commits were pushed.** `main` has the reminders commit (d57c29e) but not the colour coding (69fe5f7) or the Board "your move in red" fix (006de3d); they're still on `move-reminders`. They need a follow-up PR.
- Not checked in a browser: the deal-page panel, and the enquiry reply on the running stack.

**Risks:**
- In production, a real agent who isn't signed in will now be played by the house on demo deals involving his clients (journaled and reset with the run).

**Recommended next task:**
- Open the follow-up PR for the two missing move-reminders commits, then this branch's PR; then the registration checklist.

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

## Related documents

- [`PRODUCT_SPEC.md`](./PRODUCT_SPEC.md): read first
- [`IMPLEMENTATION_STATUS.md`](./IMPLEMENTATION_STATUS.md): verified state and gaps
- [`CHANGELOG.md`](./CHANGELOG.md): history
