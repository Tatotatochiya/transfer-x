---
title: "ADR 0008: One Conversation Per Transfer, Read Across the Existing Message Stores"
last_updated: 2026-10-04
status: Accepted
owner: "TODO — assign a Technical Owner"
---

# ADR 0008: One Conversation Per Transfer, Read Across the Existing Message Stores

## Context

Phase 3 of the [Q4 plan](../../feature_spec/phased-plan-2026-q4/README.md) gives each transfer one conversation ([product ADR 0008](../../product/decisions/0008-transfers-board-one-way-to-buy-lite-decides.md)). Its messages lived in four stores, each with its own rules:

| Store | Who reads it | Masking |
|---|---|---|
| `enquiry_messages` | both clubs | anonymous asking club masked |
| `offer_messages` | both clubs | anonymous buyer masked until acceptance ([ADR 0004](./0004-anonymous-buyer-masked-server-side.md)) |
| `deal_comments` | SHARED: both clubs, agent, player; BUYER_ONLY / SELLER_ONLY: one club | none (accepted) |
| `negotiation_messages` | CLUB_SIDE: both clubs and the agent; PLAYER_SIDE: agent and player | none |

The plan said existing messages would move into one table.

## Decision

The conversation is **read across the four stores**, not copied into a new one (`backend/app/conversation`).

- A transfer is the enquiries, offers and deals between the same two clubs about the same player.
- `GET /conversation?offer_id|deal_id|enquiry_id` merges their messages in time order. Each store's own visibility and masking rules filter them. Each message carries its audience: both clubs, everyone on the deal, only your club, or both clubs and the agent.
- `POST /conversation` writes through the store that owns the audience right now: the open offer's or enquiry's messages before a deal; the deal room (shared or private) or the agent's club thread after it. Each store's own notifications, audit and permission checks therefore run unchanged.
- The agent–player thread (PLAYER_SIDE) never appears to clubs.

## Why not one table now

- **Confidentiality.** A copy would have to re-implement four sets of visibility and masking rules. Any slip leaks an anonymous buyer or a club's private note. Reading through each store's own rules can't drift from them.
- **Behaviour.** Writes go through the existing paths, so notifications, pushes, audit and the AI-draft tracking on the old pages keep working with nothing to dual-write.
- **Nothing to migrate.** The old pages keep working while the board ships alongside them (product ADR 0008, decision 4).

## Consequences

- Storage consolidates when the old pages are retired: one table, the four stores migrated into it, and the conversation module reading from it. The API (`/conversation`) doesn't change when that happens.
- Private notes exist only once there's a deal (the deal room's club-only channel). A private note before a deal needs the consolidated table.
- Agents and players keep their existing views (the deal room and the negotiation threads) for now.
