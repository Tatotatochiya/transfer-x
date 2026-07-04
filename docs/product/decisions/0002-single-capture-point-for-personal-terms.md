---
title: "ADR 0002: Personal Terms Are Captured Once, Not Duplicated Across Negotiation and Consent"
last_updated: 2026-07-04
status: Accepted
owner: "TODO — assign a Product Owner"
---

# ADR 0002: Personal Terms Are Captured Once, Not Duplicated Across Negotiation and Consent

## Context

For a mandated deal, `AGENT_NEGOTIATION` originally captured wage/signing bonus/contract length *and* a player-side agreement status on `AgentNegotiation`, then `PERSONAL_TERMS` captured the same three fields *and* a separate consent status again on `PersonalTerms`. ADR 0001 named this as a known gap: the agent had to re-enter the same figures a second time, since nothing copied them across. Manually testing the flow surfaced the actual size of the problem — an agent proposing terms as "2% of the fee" during negotiation had no equivalent step for personal terms either, and the two `player_agreement` / `player_consent` statuses could disagree with nothing reconciling them.

## Decision

Personal terms are captured exactly once, at `PERSONAL_TERMS`, regardless of whether the deal is mandated. `AGENT_NEGOTIATION` now negotiates commission with the buying club only. Concretely:

- `AgentNegotiation` dropped `proposed_wage_weekly`, `proposed_signing_bonus`, `proposed_length_years`, and `player_agreement` (migration `0047`) — commission-only.
- Advancing `AGENT_NEGOTIATION → PERSONAL_TERMS` now requires only `club_agreement == AGREED` (previously also required the now-removed `player_agreement`).
- The `POST /deals/{id}/agent-negotiation/player-respond` endpoint was removed entirely — there is no player-side action at this stage anymore.
- `player_consent_to_terms` (`PERSONAL_TERMS`) is the one remaining consent point, and picked up the account-gated proxy rule from ADR-adjacent work in the same session: the player consents themselves if they have an account; the mandated agent may act as proxy only if the player has none at all (mirrors the same rule already used for the club-side of `AGENT_NEGOTIATION`). This applies uniformly to mandated and non-mandated deals — there's no longer a second, inconsistent gate to keep in sync.

## Alternatives considered

- **Copy the agent-negotiated figures into `PersonalTerms` on the stage transition** (ADR 0001's original framing of the gap). Rejected: this fixes the "re-typing" annoyance but keeps two consent statuses that could still drift, and keeps `AgentNegotiation` carrying data it doesn't need to own. Removing the duplication outright is a smaller surface to reason about than keeping two synchronized copies.
- **Let the agent's `AGENT_NEGOTIATION` player-side agreement count as final consent**, skipping a separate `PERSONAL_TERMS` consent step for mandated deals. Rejected: this would mean an account-holding player is never asked to agree to their own contract at all when represented by an agent — real personal terms require the player's own sign-off, agent or not (the same principle ADR 0001 and TRA-60 already established for the non-mandated path).

## Consequences

- Resolves the "known gap, not addressed" note in ADR 0001 — there is nothing left to copy, since there's only one place these figures are ever entered.
- `AgentNegotiationResponse` no longer exposes `player_agreement`/`proposed_*` fields; any frontend code reading them was updated in the same change (`AgentNegotiationWorkspace`, `PlayerTermsProposalView` — the latter removed entirely).
- The account-gated proxy rule (real player consents if they have an account; mandated agent proxies only if they don't) is now the *only* rule governing personal-terms consent, for both mandated and non-mandated deals, rather than one rule at `AGENT_NEGOTIATION` and a looser, unconditional one at `PERSONAL_TERMS`.

## Related documents

- [`0001-buying-club-proposes-personal-terms.md`](./0001-buying-club-proposes-personal-terms.md) — the decision this one resolves the noted gap in
- [`../workflows/transfer-lifecycle.md`](../workflows/transfer-lifecycle.md) — updated stage description
- [`../workflows/agent-representation.md`](../workflows/agent-representation.md) — updated `AGENT_NEGOTIATION` scope
- [`../../CHANGELOG.md`](../../CHANGELOG.md) — the change entry
