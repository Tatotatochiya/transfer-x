---
title: "Session Handover"
last_updated: 2026-09-28
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

## Session Summary — 2026-09-28

**Where the work is.**
- Branch **`player-invitations`**, off `main` at `b85c0cb` (PRs #3–#7 merged). It holds player accounts by invitation, the agent rule change and this handover, all **uncommitted**.
- The local database is at migration head `0082`.
- `gh` is authenticated on this machine, so pushing and opening PRs work from here.
- Commits are authored per command as `Tatotatochiya <aashishpradhan@outlook.com>`, because this machine has no git identity configured.

**Completed work** (PRs #3–#7; detail in [`CHANGELOG.md`](./CHANGELOG.md)):

- **Deals** (PRs #3–#4):
  - Terms the player consented to become the deal's contract.
  - The payment structure (instalments, add-ons, sell-on) is agreed on the offer.
  - The market has a "buyable" filter, and offers are refused for players at clubs outside TransferX.
  - Daily digest and "your move" emails, with Mailpit for local mail.
  - Row locks on the money paths (audit H3 — done).
  - Club-run paperwork checklist.
- **Simplify and onboard** (PR #5):
  - Navigation grouped Home / Buying / Selling / Club.
  - One kind of listing, and "open to offers" now means listed (product ADR 0005).
  - One page per transfer.
  - Clubs join by invitation only (`/join`).
  - Enquiries.
- **Clubs complete transfers without staff** (PR #6):
  - Clubs run deals won at auction themselves.
  - Honest Personal Terms states.
  - The buying club records consent for a player with no account or agent (product ADR 0006).
- **AI assistant across the workflow** (PR #7, architecture ADR 0006):
  - Offer advisor, terms checks and negotiation summary.
  - Deal next steps.
  - Morning briefing on the War Room and in the digest.
  - Pricing assistant and "Who might want him?".
  - Ask TransferX (⌘K).
- **Player accounts by invitation** (branch `player-invitations`, [ADR 0007](./product/decisions/0007-players-join-by-invitation-agents-can-answer.md)):
  - The owning club invites from the player's page, and `/join/player` creates a verified account.
  - Player self-registration is refused.
  - A mandated agent can answer terms whether or not the player has an account.
  - Club players' profiles no longer offer the refused "Open to offers" switch.
- **Also in PR #7:**
  - Anonymous-buyer fixes: the War Room leak, and the label naming a competition (`Club.masking_league`).
  - Signed terms required when the club records consent (migration `0081`).
  - 41 new tests.

**Important decisions** (all with the product owner):

- Clubs join by invitation only; `ALLOW_CLUB_SELF_REGISTRATION` exists for tests.
- Consent for a player with no account and no agent is recorded by the buying club, with the signed terms attached.
- **Players join only by invitation from their club** (not an agent, and no self-sign-up). A mandated agent can always answer personal terms for his client, even when the player has an account (ADR 0007).
- The AI advises and never acts: facts are scoped server-side, figures are computed by TransferX, and model output is validated.
- Swaps are deferred.

**Outstanding work:**

- **Commit `player-invitations`, then push and open its PR.**
- **Free agents can't join yet.** Player invitations come only from the owning club (TODO in ADR 0007).
- **Test data left in the dev database.**
  - My live checks from 27–28 Sept left 7 deals, 9 offers, 5 auction listings, 3 enquiries and 2 "Test FC" clubs.
  - Their money is already released (the deals are collapsed, the offer withdrawn, the listings withdrawn).
  - Deleting the rows was refused by the permission check as a mass delete, so it's the product owner's call.
- **Contract end dates are missing for whole squads** (e.g. Liverpool has none), which weakens the expiring-contracts panel, the briefing, "Who might want him?" and the pricing assistant.
- **The AI cache and rate limit are in memory.** A shared store is needed before running several API processes.
- **Not built from the AI ideas list:** offer builder, approvals brief, finance forecast, deal document drafts.
- **No production environment.**
- **Railway:**
  - Migrations `0071`–`0081` are likely pending (Railway does not auto-deploy); check the live `alembic_version`.
  - `backfill_contract_wages.py` is still required there before loans work.
- Still open from earlier handovers:
  - Conditional obligation to buy: automatic start or both-club confirmation?
  - A player out on loan can't be listed from the "Out on loan" panel.
  - The dead `sort_by=value` market sort.
  - The demo generator's unbuilt M1–M4/S1–S2 scenarios.

**Risks:**

- **The frontend is a built image.** New UI needs `docker compose build frontend && docker compose up -d frontend`. The API mounts the source and runs migrations on `docker compose restart api`.
- **The dev `.env` sets `LLM_MODEL` to DeepSeek.** The code default is `claude-sonnet-5`. Tests never call a model.
- **Consent recorded by a club is only as good as the signed copy it attaches.** The platform does not verify signatures.

**Checks, as of 2026-09-28:**

- Backend: 578 passed.
- vitest: 136 passed. (Backend now 585 with the player-invitation tests.)
- `tsc -b`: 42 errors, all pre-existing.

**Recommended next task:**

1. Commit and PR `player-invitations`.
2. Then either the contract-end-date backfill, or the production environment (with the shared AI store).

**Suggested Linear updates** (not made; for the product owner to confirm):

- Close the tickets covered by PRs #3–#7: audit H3, club-run paperwork, invite-only onboarding, enquiries, the AI assistant.
- New: "How free agents join TransferX"; "Backfill contract end dates"; "Shared store for AI cache and rate limit"; "Production environment".

## Related documents

- [`PRODUCT_SPEC.md`](./PRODUCT_SPEC.md) — read this first, then this file
- [`CHANGELOG.md`](./CHANGELOG.md) — full change history
- [`IMPLEMENTATION_STATUS.md`](./IMPLEMENTATION_STATUS.md) — current verified build status
