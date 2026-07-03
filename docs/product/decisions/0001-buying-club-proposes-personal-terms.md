---
title: "ADR 0001: Buying Club Proposes Personal Terms in Non-Mandated Deals"
last_updated: 2026-07-04
status: Accepted
owner: "TODO — assign a Product Owner"
---

# ADR 0001: Buying Club Proposes Personal Terms in Non-Mandated Deals

## Context

TRA-60's original spec called for letting the player act directly to propose their own personal terms (wage, signing bonus, contract length) when a deal has no mandated agent. While fixing a regression where such deals skipped the `PERSONAL_TERMS` consent stage entirely (see [`docs/CHANGELOG.md`](../../CHANGELOG.md)), this needed a concrete answer: who proposes terms when there's no agent to do it?

## Decision

The **buying club** proposes personal terms; the **player** consents or declines. This mirrors the mandated-agent path, where the agent negotiates *with* the club rather than the player self-assigning terms, and matches how contract offers work in practice — the employer proposes, the employee accepts or declines.

Implemented in `set_personal_terms` (`backend/app/deals/router.py`): the endpoint accepts a request from the buying club (via `clubs_service.get_club_for_user`) in addition to a mandated agent. The player-consent endpoint was already correctly open to the player directly and was not changed.

## Alternatives considered

- **Player proposes their own terms** (the original TRA-60 spec). Rejected: doesn't match how the agent path works — there, the club/agent proposes and the player consents, not the player proposing to themselves. It would also require the player to enter a wage figure with no counterpart having agreed to it first, which isn't a real negotiation.

## Consequences

- Consistent mental model across both paths: a club-side actor (buying club or agent) proposes, the player consents. Future UI/permissions work can treat "who can call `set_personal_terms`" uniformly.
- Known gap, not addressed by this decision: when a mandated deal advances `AGENT_NEGOTIATION → PERSONAL_TERMS`, the agent-negotiated `proposed_wage_weekly` / `proposed_signing_bonus` / `proposed_length_years` are not copied into the new `PersonalTerms` record, so the agent must re-enter the same figures a second time. Not yet ticketed.

## Related documents

- [`docs/product/workflows/transfer-lifecycle.md`](../workflows/transfer-lifecycle.md) — the workflow this decision affects
- [`docs/CHANGELOG.md`](../../CHANGELOG.md) — the TRA-60 fix this decision was made as part of
