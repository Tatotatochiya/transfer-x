---
title: "Feature Specs"
last_updated: 2026-07-10
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

| Spec | Linear | Status |
|---|---|---|
| [Fair-Value-vs-Asking Signal](./fair-value-vs-asking-signal.md) | TRA-91 (backend), TRA-92 (UI) | Implemented 2026-07-07 — see the spec's "Deviations from spec" section |
| [Injury-Availability Risk Profile](./injury-availability-risk-profile.md) | No ticket yet — proposed 2026-07-05 (see spec's reconciliation section) | Active — ready to implement |
| [Club Team Accounts, Roles & Onboarding](./club-team-roles-and-onboarding.md) | TRA-151, TRA-146, TRA-152, TRA-86 (phases 1–4) + two proposed tickets (phases 5–6) | Implemented 2026-07-10 (all six phases) — see the spec's "Deviations from spec" section |

## Related documents

- [`../README.md`](../README.md) — documentation system conventions
- [`../product/roadmap.md`](../product/roadmap.md) — where these features sit in the plan
