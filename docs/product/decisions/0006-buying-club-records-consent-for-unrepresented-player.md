---
title: "ADR 0006: The Buying Club Records Consent for a Player With No Account or Agent"
last_updated: 2026-09-28
status: Accepted
owner: "TODO — assign a Product Owner"
---

# ADR 0006: The Buying Club Records Consent for a Player With No Account or Agent

## Context

A deal cannot leave `PERSONAL_TERMS` until the player consents to the proposed terms. [ADR 0002](./0002-single-capture-point-for-personal-terms.md) settled who may consent:
- the player, if he has an account;
- otherwise his mandated agent.

A player with neither could only have his answer recorded by TransferX staff. Most players on the platform are in that position. So even after the clubs took over the paperwork and auction deals, most transfers still waited on staff at this one step.

## Decision

1. **When the player has no account and no agent, the buying club records his answer.** In a real transfer the buying club agrees personal terms with the player directly, so it is the party that actually has the answer.
2. **Only the buying club, and only a member with deal-write permission,** can record it. The selling club and third clubs are refused.
   - If the player has an account, he answers himself.
   - If he has an agent on the terms, the agent answers.
3. **The record says who made it.** The audit entry reads "Buying club recorded that the player agreed…" (payload `recorded_by: BUYING_CLUB`). The selling club is notified in the same words.
4. **The UI makes it a deliberate act.** The buyer confirms that the player agreed, and recording a decline warns that it collapses the deal.
5. **Recording an agreement needs the signed terms** (added 2026-09-28, migration `0081`).
   - The buying club uploads the signed copy to its private deal-room channel. The file holds the player's wage, which the selling club doesn't need.
   - The consent record points to that document, and so does the audit entry.
   - The document must be one the buying club uploaded to this deal.
   - New terms clear the signed copy along with the consent.
   - Recording a decline needs no document.

## Consequences

- A transfer can run end to end with no TransferX staff involved.
- The consent is the buying club's word, not the player's own login, but it now rests on the signed copy it attached. The platform still cannot verify the signature itself.


- Staff keep their override, unchanged.

## Alternatives considered

- **Keep staff as the recorder.** This is the most verifiable option, but it keeps TransferX in nearly every deal. Rejected.
- **Invite the player to create an account to consent.** It is right for the long term, but there is no player onboarding by invitation yet, and it would stall deals until there is.
