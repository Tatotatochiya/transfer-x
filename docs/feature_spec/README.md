---
title: "Feature Specs"
last_updated: 2026-10-11
status: Active
owner: "TODO — assign a Product Owner"
---

# Feature Specs

## Purpose

Implementation-ready specifications for upcoming builds — the bridge between a Linear ticket (which says *what and why*, briefly) and the code (which says *how*, after the fact). A spec in this folder is written so that an engineer or an AI coding agent with no prior context can implement the feature and verify their work against the spec's success criteria, without needing the conversation that produced it.

## Scope

In scope: one file per feature, containing decided scope, exact data/model/API/UI specifications, worked examples, and success criteria to review an implementation against.
Out of scope: current-state documentation (that's the six main areas — see [`../README.md`](../README.md)), ticket-level tracking (Linear), decision records for shipped work ([`../product/decisions/`](../product/decisions/README.md) and [`../architecture/decisions/`](../architecture/decisions/README.md)).

## How specs relate to the rest of `/docs`

A spec is a **point-in-time build document, not living state**. To keep it from becoming a second, conflicting source of truth:

- While a feature is unbuilt, its spec is the authority on what to build (`status: Active`).
- Once shipped, the implementer updates the product/architecture/engineering docs per the [`documentation-standards`](../../.claude/skills/documentation-standards/SKILL.md) skill, sets the spec's `status` to `Implemented`, and from then on the main docs are the truth — the spec is kept for history and review context only.
- If implementation deviates from the spec, record the deviation in the spec's changelog section before marking it `Implemented` — don't leave the spec silently wrong.

## Specs

Statuses verified against the code and `CHANGELOG.md` on 2026-10-11. Once a spec is implemented, the main docs are the truth and the spec is kept for its decisions, rules and deviations. Build-only files (HTML prototypes, session plans, screenshots) are removed after shipping; git history keeps them.

**In progress or planned**

| Spec | Status |
|---|---|
| [`phased-plan-2026-q4/`](./phased-plan-2026-q4/README.md): the current plan, Phase 0 to Phase 5, and the decisions needed. [Phase 0 runbook](./phased-plan-2026-q4/phase-0-runbook.md) for the real-phone test | Active: Phases 0, 1 and 3 done (except the phone test and two-factor sign-in); 2, 4, 5 not started |
| [`ai-analyst/`](./ai-analyst/README.md): Ask TransferX as an analyst: read-only, club-scoped tools, tables, charts, Excel, "Ask about this" | Phases A and B built; Phase C not started |
| [`valuation-model-v2.md`](./valuation-model-v2.md): the `market-v2` fair-value model | Shipped 2026-10-07; calibrated 2026-10-17 |
| [`scheduled-data-refresh.md`](./scheduled-data-refresh.md): twice-daily API-Football refresh in the `stats-worker`, Admin Jobs and Errors, request health, Slack | Live 2026-10-11; Slack webhook pending |
| [`injury-availability-risk-profile.md`](./injury-availability-risk-profile.md): an availability risk score per player | Not built as specified (availability is on the ledger and in the valuation) |
| [`demo-scenario-generator.md`](./demo-scenario-generator.md): demo deals at every stage | Phase 1 built; M1–M4, S1–S2 not built |
| [`demo-mode.md`](./demo-mode.md): try transfers on real data against house clubs, then reset | Step 1 built (runs, journal, reset, play-as) |

**Implemented (kept for decisions, rules and deviations)**

| Spec | Implemented |
|---|---|
| [`lite-mode/`](./lite-mode/README.md) (with [`BACKEND.md`](./lite-mode/BACKEND.md)): Lite mode for directors | 2026-10-04, L1–L8 |
| [`mobile-notifications/`](./mobile-notifications/README.md) (with `HANDOFF.md`): phone notifications | 2026-10-04 |
| [`player-profile-ledger/`](./player-profile-ledger/README.md) (with `HANDOFF.md`, cited by the code): the season ledger | 2026-10-01 |
| [`my-club-compact-squad/`](./my-club-compact-squad/README.md) | 2026-10-02 |
| [`compact-sidebar/`](./compact-sidebar/README.md) | 2026-10-02 |
| [`loan-transfers.md`](./loan-transfers.md) | 2026-08-25 to 09-28 |
| [`club-team-roles-and-onboarding.md`](./club-team-roles-and-onboarding.md) | 2026-07-10 |
| [`fair-value-vs-asking-signal.md`](./fair-value-vs-asking-signal.md): the signal, endpoints and rules (the engine is now v2) | 2026-07-07 |

## Related documents

- [`../README.md`](../README.md) — documentation system conventions
- [`../product/roadmap.md`](../product/roadmap.md) — where these features sit in the plan
