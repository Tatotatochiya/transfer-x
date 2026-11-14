---
title: "ADR 0012: The Agent's Commission and Personal Terms Are Negotiated, and Ending a Transfer Is Confirmed"
last_updated: 2026-11-14
status: Accepted
owner: "TODO — assign a Product Owner"
---

# ADR 0012: The Agent's Commission and Personal Terms Are Negotiated, and Ending a Transfer Is Confirmed

## Context

At `AGENT_NEGOTIATION` the buying club could only accept or decline the agent's commission, and a decline collapsed the deal. The deal card then said "the agent can send a new proposal", which wasn't true. At `PERSONAL_TERMS` the player's side could only agree or decline the terms, and a decline also ended the transfer. With an agent, the agent proposed the player's terms and then agreed them himself, so the buying club, which pays the wage, never agreed to them. Three of the answers that end a transfer went through with one click and no confirmation.

Real negotiations go back and forth: a club offers 3% where an agent asks for 8%, an agent asks for a higher wage or a fifth year.

## Decision

1. **Commission is negotiated.** The agent proposes; the buying club **accepts**, **counters** (a percentage and who pays, with an optional note) or **declines**. A counter is the agent's to accept or answer with a new proposal. There's no limit on rounds.
2. **Personal terms are negotiated between the buying club and the player's side** (the player, or his agent). Whoever proposes, the other side accepts, counters or declines. The agent's terms, or the player's counter, are the buying club's to answer; the club's terms are the player side's to answer, as before ([ADR 0006](./0006-buying-club-records-consent-for-unrepresented-player.md), [ADR 0007](./0007-players-join-by-invitation-agents-can-answer.md)). `player_consent` AGREED now means both sides agreed. The player's agent stays on terms the club proposes, and answers them for his client.
3. **Declining is walking away**, and ends the transfer as before. Every answer that ends a transfer opens the same confirmation (`EndTransferDialog`): it says the deal collapses and who is told, offers **Counter instead** where a counter is possible, and takes an optional reason that both sides see, as a collapse reason is.
4. **Every round is kept** (`term_proposals`) and shown on the deal card as "The negotiation so far". Commission rounds are the buying club's and the agent's business: the selling club and the player don't see them, as they don't see the commission.

## Alternatives considered

- **Keep accept-or-decline, and fix only the card's wording.** Rejected: it leaves a club that wants to negotiate with only the deal room's messages and a collapse, and the wage still goes unagreed by the club that pays it.
- **Let a decline stay soft (the agent proposes again) instead of adding counters.** Rejected: a decline that doesn't end anything is a counter without a figure, and leaves no way to walk away short of collapsing the deal.
- **Cap the rounds.** Not needed: either side can walk away at any point.

## Consequences

- `agent_negotiations.proposed_by` and `personal_terms.proposed_by` say whose terms are on the table; rows from before default to the old meaning (the agent's commission; terms for the player side to answer). Migration `0113`.
- New endpoints: `POST /deals/{id}/agent-negotiation/club-counter`, `…/agent-accept`, `POST /deals/{id}/personal-terms/club-respond`, `GET /deals/{id}/term-proposals`; `PUT /deals/{id}/personal-terms` takes a note and accepts the player's own counter.
- Move reminders follow the new holders: the agent holds a club's counter; the buying club holds the player side's terms.
- In demos the house agent answers counters (accepting within a point of 5%, otherwise meeting halfway), and the player's side answers the club's terms (accepting 95% of its ask, otherwise meeting halfway); after two rounds either takes what's offered.

## Related documents

- [`../workflows/transfer-lifecycle.md`](../workflows/transfer-lifecycle.md), [`../workflows/agent-representation.md`](../workflows/agent-representation.md)
- [`../../design-system/README.md`](../../design-system/README.md) — "Ending a transfer"
