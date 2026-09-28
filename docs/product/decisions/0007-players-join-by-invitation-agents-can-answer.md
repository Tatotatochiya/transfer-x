---
title: "ADR 0007: Players Join by Invitation From Their Club; a Mandated Agent Can Always Answer"
last_updated: 2026-09-28
status: Accepted
owner: "TODO — assign a Product Owner"
---

# ADR 0007: Players Join by Invitation From Their Club; a Mandated Agent Can Always Answer

## Context

A player account can accept personal terms, which binds the player to a contract. Until now anyone could register as a player by picking a player record by name. Nothing checked that the person was that player.

Consent rules before this decision:
- a player with an account answered his own terms;
- a mandated agent could answer only for a player **without** an account ([ADR 0002](./0002-single-capture-point-for-personal-terms.md));
- with neither, the buying club recorded the answer, with the signed terms ([ADR 0006](./0006-buying-club-records-consent-for-unrepresented-player.md)).

## Decision

1. **Players join by invitation from the club that owns them**, the same way clubs and staff join.
   - The owning club invites from the player's page: Player account → Invite.
   - Inviting needs the team-management permission, as inviting staff does.
   - The player accepts at `/join/player?token=…`. That creates his PLAYER account, linked to his record and marked verified, since the club vouched for the email.
   - Invitations work once, expire after 7 days, can be revoked, and only the token's hash is stored (migration `0082`).
   - Registering as a player is refused (403). `ALLOW_PLAYER_SELF_REGISTRATION` exists for tests.
2. **A mandated agent can always answer personal terms for his client, whether or not the player has an account.** Representing the player is what the mandate is for. The player can still answer himself, and whichever answers first decides.
3. **Recording by the buying club is unchanged.** It applies only when the player has neither an account nor an agent on the terms.

## Consequences

- A player can no longer be impersonated by picking his name at sign-up.
- A player can't join until his club invites him. A free agent, with no club, has no way in for now.

> **TODO:** decide how free agents join (an agent's invitation, or TransferX staff).

- An agent answering for a client who has an account is audited as the agent's action. The player sees the result on his profile.
