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

## Session Summary — 2026-11-14 (adopting a deal into a demo; the Transfers board on phones)

**Completed work:**
- Merged today: #73 (reminder colours), #74 (counters and confirmed declines, ADR 0012), #75 (whose move from `proposed_by`), #76 (the deal page updates live during a negotiation).
- Branch `demo-adopt`: a deal outside any demo (a seeded scenario deal, say) can be added to your open demo from its page ("Add to my demo"). TransferX then plays its agent and player, "Make them move now" and reminders work, and Reset puts it back. Done as a journal `adopt` entry (`journal.RUN_ROW_OPS`), no migration. Checked on the stack: adopted a Chelsea–Arsenal deal, the house agent proposed, Reset restored it.
- Branch `transfers-board-mobile` (from `README_TRANSFERS.md`, 14 Nov): below 1280px the board is a list grouped by whose move it is, with stage bars, stage chips (`?stage=`), a ⋯ menu; from 1280px empty columns collapse and a "Waiting on you" strip sits above the lanes; the name banner shows on the Dashboard only. First row at 297px on a 390 phone; nothing under 13px. Spec filed under `docs/feature_spec/transfers-board-mobile/` with its deviations.
- `README_TRANSFER.md` (9 Nov, Browse Players) was already built (PRs #65, #66).
- Tests: `demo-adopt` backend 970 passed, frontend 503; `transfers-board-mobile` frontend 519.

**Important decisions:**
- An adopted deal is played only on its agent's and player's side (and a house club's, if one is party), never a club people use.

**Outstanding work:**
- Both branches open as PRs; they touch different code (docs overlap in CHANGELOG only).
- Whether Railway's email is real or caught: a reminder escalated to a seeded agent (`james.mitchell@elitesports.com`) may have gone to a real domain.

**Risks:**
- A deal adopted into a demo is refused to anyone outside that demo until it's reset (as every demo row is).

**Recommended next task:**
- The registration checklist.

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

## Related documents

- [`PRODUCT_SPEC.md`](./PRODUCT_SPEC.md): read first
- [`IMPLEMENTATION_STATUS.md`](./IMPLEMENTATION_STATUS.md): verified state and gaps
- [`CHANGELOG.md`](./CHANGELOG.md): history
