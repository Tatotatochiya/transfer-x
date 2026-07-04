---
title: "Implementation Status"
last_updated: 2026-07-04
status: Active
owner: "TODO — assign a Documentation Owner"
---

# Implementation Status

## Purpose

A living snapshot of what's actually built in TransferX right now, **verified against the code** — not a restatement of what Linear tickets claim, and not a history of changes (see [`CHANGELOG.md`](./CHANGELOG.md) for that).

## Scope

In scope: current, verified build status by area.
Out of scope: the plan/roadmap (see [`product/roadmap.md`](./product/roadmap.md)), ticket-level detail (Linear is the source of truth for that), a chronological log of changes (see [`CHANGELOG.md`](./CHANGELOG.md)).

## Why "verified" matters here

A Linear ticket marked Done is a claim, not a guarantee — a later change can silently break an earlier ticket's promise without either ticket's status reflecting it. This file exists specifically to hold the *checked* answer, which sometimes differs from what the backlog says. If you're updating a row below, that means you looked at the actual code for that area during this session, not that you copied a ticket's status.

Maintained by the [`documentation-standards`](../.claude/skills/documentation-standards/SKILL.md) skill.

## Status by area

| Area | Status | Last verified | Notes |
|---|---|---|---|
| Documentation system (`/docs`) | Built | 2026-07-03 | This structure and its conventions. |
| Claude Code project skills (`.claude/skills/`) | Built | 2026-07-03 | Five skills — see [`docs/README.md`](./README.md). |
| Marketplace Core — Phase 3 (player consent) | Fixed | 2026-07-03 | A non-mandated deal skipped `PERSONAL_TERMS` entirely (TRA-60 regression). Fixed; the buying club can now propose terms and the player consents directly. Covered by `backend/tests/test_deals.py`. |
| Marketplace Core — Phase 4 (trust foundation) | Fixed | 2026-07-04 | TRA-127 (agent-negotiation hijack) and the five access-control gaps from the workflow audit — TRA-137 (deal access for agent/player), TRA-138 (seller-ownership validation), TRA-139 (public reserve-price/bid leak), TRA-140 (medical/personal-terms exposure), TRA-141 (audit-log scoping) — are all fixed and regression-tested. The audit log is now comprehensive (every deal-mutating action emits an event) and actor-attributed (`actor_user_id` was always null before this session; now populated everywhere, with labels resolved in both the JSON endpoint and CSV export). Verified boundary table: [`security-and-compliance/permissions-model.md`](./security-and-compliance/permissions-model.md). Remaining Phase 4 items: TRA-143 (player identity attestation), TRA-144 (mandate player-confirmation), TRA-146 (club-staff deal access) — see Linear. |
| Marketplace Core — Phase 2 (deal structure) | Fixed (commission) | 2026-07-04 | Commission was only tracked if the agent manually entered an absolute amount alongside the percentage — no `AgentCommission` record was created otherwise, silently. Now auto-derives the amount from `commission_pct × agreed_fee` whenever only a percentage is given. Rest of Phase 2 (loans, add-ons, sell-on, instalments) not independently re-verified this session. |
| Marketplace Core — Phase 3 (player consent) | Reworked | 2026-07-04 | Personal terms used to be captured twice — once (informally) during `AGENT_NEGOTIATION`, again at `PERSONAL_TERMS` — with no reconciliation between the two consent statuses. Per [ADR 0002](./product/decisions/0002-single-capture-point-for-personal-terms.md), now captured exactly once, at `PERSONAL_TERMS`, for both mandated and non-mandated deals, with one consistent account-gated proxy rule (real player consents if they have an account; mandated agent proxies only if they don't). |
| Marketplace Core — Phase 0–2 (finance, actors) | TODO | — | Not independently re-verified this session (commission handling above is the one Phase 2 exception); see [`product/roadmap.md`](./product/roadmap.md). |
| Agent Experience — Milestone 3 (manage deals end to end) | Fixed | 2026-07-04 | Several real bugs found by manually driving the flow, not caught by Linear's "shipped" status: an invited agent couldn't open the deal room before their first negotiation write (deadlock); the agent couldn't trigger `AGENT_NEGOTIATION → PERSONAL_TERMS` (club-only bug); a club couldn't advance `PERSONAL_TERMS → PAPERWORK` either (frontend gating bug); `set_personal_terms` accepted any agent, not just the mandated one; agent invitations kept showing for already-collapsed/completed deals. All fixed and regression-tested. |
| Agent Experience — Milestones 1, 2, 4, 5 | TODO | — | Not independently re-verified this session. |
| Differentiation & Demo Readiness | TODO | — | |
| Production & Business Readiness | TODO | — | Known accurate as of the last check: no production environment is configured yet (see [`operations/environments-and-deployment.md`](./operations/environments-and-deployment.md)). |

> **TODO:** This table is intentionally sparse on first creation rather than guessed at wholesale. Fill in a row properly (with a real verification date) the next time a session does substantive work in that area — don't backfill the rest from memory in one sitting, since that reintroduces the exact "unverified claim" problem this document exists to avoid.

## Related documents

- [`CHANGELOG.md`](./CHANGELOG.md) — the history of changes, as distinct from this current-state snapshot
- [`PRODUCT_SPEC.md`](./PRODUCT_SPEC.md) — master index and high-level current-state table
- [`product/roadmap.md`](./product/roadmap.md) — the plan this status is measured against
