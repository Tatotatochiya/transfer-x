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
4. **A free agent is invited by TransferX staff, or by his agent** (added 2026-09-28, migration `0083`).
   - A free agent has no club to invite him.
   - Staff invite from the admin player page. His mandated agent invites from the client page, and needs an active mandate.
   - Only a genuine free agent (status FREE_AGENT) qualifies. A player at a club outside TransferX (EXTERNAL) is not one ([architecture ADR 0003](../../architecture/decisions/0003-player-status-distinguishes-external-clubs.md)).
   - A player at a TransferX club is always his club's to invite.

## Consequences

- A player can no longer be impersonated by picking his name at sign-up.
- A player can't join until someone accountable invites him: his club, or for a free agent his agent or TransferX.

- An agent answering for a client who has an account is audited as the agent's action. The player sees the result on his profile.
