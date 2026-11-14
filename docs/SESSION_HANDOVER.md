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

## Session Summary — 2026-11-14 (counters and confirmed declines)

**Completed work:**
- PR #73 (reminder colour coding and the Board's red "your move", missed from #71) opened, with `MOVE_STALLED` moved to migration `0112` because `0111` had shipped.
- Branch `counters` (on top of #73): [product ADR 0012](./product/decisions/0012-commission-and-personal-terms-are-negotiated.md).
  - The buying club counters the agent's commission; the agent accepts or proposes again.
  - Personal terms go back and forth between the buying club and the player's side; the agent's terms are now the club's to answer (before, the agent proposed and agreed them himself).
  - Every round is kept (`term_proposals`, migration `0113`) and shown as "The negotiation so far".
  - Every answer that ends a transfer goes through `EndTransferDialog` (reason, "Counter instead"); `src/test/endTransfer.test.ts` guards it.
  - The card no longer says "the agent can send a new proposal" after a decline that had collapsed the deal.
  - The demo house agent and player negotiate counters.
- Checked on the running stack in a demo (Chelsea for I. Maatsen): the commission card, decline dialog, phone counter form, a 2% counter answered at 3.5% with the history, the agent's terms card and its decline dialog.
- Tests: backend 965 passed, frontend 498 passed, `tsc -b` clean.

**Important decisions:**
- ADR 0012. `player_consent` AGREED now means both sides agreed the terms. Old rows without `proposed_by` keep the old meaning.

**Outstanding work:**
- Merge #73 before this branch (it carries #73's commits until then).
- Branch `whose-move` (on top of #74): whose move follows `proposed_by` on the Board, the Dashboard and deal lists; the Dashboard reads the server's `whose_move`, and the frontend copy of the deal rule is gone. Merge order: #73, #74, then this.
- Branch `negotiation-live`: the deal page updates live on every negotiation action and house move (`deals/live.py`); a round counts as movement (the demo journal now skips `deals.updated_at`, like `users.last_active_at`).
- The local frontend container serves a built bundle: `docker compose build frontend` after frontend changes.

**Risks:**
- In-flight production deals whose agent proposed terms before this change: `proposed_by` is null, read as the club's terms, so the agent can still agree them as before.

**Recommended next task:**
- The registration checklist.

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

## Related documents

- [`PRODUCT_SPEC.md`](./PRODUCT_SPEC.md): read first
- [`IMPLEMENTATION_STATUS.md`](./IMPLEMENTATION_STATUS.md): verified state and gaps
- [`CHANGELOG.md`](./CHANGELOG.md): history
