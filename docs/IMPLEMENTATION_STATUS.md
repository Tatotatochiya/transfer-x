---
title: "Implementation Status"
last_updated: 2026-07-03
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
| Marketplace Core — Phase 4 (trust: agent-negotiation authorization) | Fixed | 2026-07-03 | Any agent could claim an unstarted negotiation for a deal they weren't invited to (TRA-127 regression). Fixed; now checked against `AgentDealInvitation`. Covered by `backend/tests/test_agent_negotiation.py`. Other Phase 4 items from the workflow audit (public reserve-price leak, medical/personal-terms exposure, seller-ownership validation, deal access for agent/player) are still open — see Linear TRA-137–140. |
| Marketplace Core — Phase 0–2 (finance, actors, deal structure) | TODO | — | Not independently re-verified this session; see [`product/roadmap.md`](./product/roadmap.md). |
| Agent Experience | TODO | — | Linear shows all five milestones shipped; not independently re-verified here yet, aside from the Phase 4 negotiation-authorization fix above (which sits in this project in Linear). |
| Differentiation & Demo Readiness | TODO | — | |
| Production & Business Readiness | TODO | — | Known accurate as of the last check: no production environment is configured yet (see [`operations/environments-and-deployment.md`](./operations/environments-and-deployment.md)). |

> **TODO:** This table is intentionally sparse on first creation rather than guessed at wholesale. Fill in a row properly (with a real verification date) the next time a session does substantive work in that area — don't backfill the rest from memory in one sitting, since that reintroduces the exact "unverified claim" problem this document exists to avoid.

## Related documents

- [`CHANGELOG.md`](./CHANGELOG.md) — the history of changes, as distinct from this current-state snapshot
- [`PRODUCT_SPEC.md`](./PRODUCT_SPEC.md) — master index and high-level current-state table
- [`product/roadmap.md`](./product/roadmap.md) — the plan this status is measured against
