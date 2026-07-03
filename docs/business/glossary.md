---
title: "Glossary"
last_updated: 2026-07-03
status: Active
owner: "TODO — assign a Documentation Owner"
---

# Glossary

## Purpose

The single canonical place domain terms are defined. Every other document should **link here** rather than redefining a term — this is how the documentation set avoids duplicate (and eventually contradictory) definitions.

## Scope

In scope: domain/business terms used across TransferX's product and documentation.
Out of scope: pure engineering jargon (framework names, library names) — those are explained where used, not here.

## Table of Contents

- [Actors](#actors)
- [Listings & bidding](#listings--bidding)
- [Negotiation](#negotiation)
- [Deals](#deals)
- [Finance](#finance)
- [Related documents](#related-documents)

## Actors

| Term | Definition |
|---|---|
| **Club** | An organization account that can buy and/or sell players. Has a role: buyer, seller, or both. |
| **Agent** | Represents one or more players under a mandate; can negotiate commission and personal terms on a player's behalf. |
| **Player** | The individual being transferred. May optionally hold their own account to manage visibility and consent directly. |
| **Staff** | A user attached to a club account with scoped permissions, distinct from the club's primary owner login. |
| **Mandate** | The formal representation relationship between an agent and a player; can be exclusive or non-exclusive, and has a validity period. |

## Listings & bidding

| Term | Definition |
|---|---|
| **Sale** | A player listing created by a selling club. Has a type: **Auction**, **Fixed Price**, or **Open to Offers**. |
| **Bid** | An amount placed by a buying club against an auction-type Sale. |
| **Reserve price** | The minimum amount a seller will accept in an auction; visible only to the seller. |
| **Order book** | The ranked view of active bids/offers on a Sale. |

## Negotiation

| Term | Definition |
|---|---|
| **Offer** | A direct proposal from a buying club to a selling club, outside the auction mechanism. Can be countered by either side. |
| **Counter** | A revised Offer responding to a previous one. |

## Deals

| Term | Definition |
|---|---|
| **Deal** | Created once a Bid or Offer is accepted; tracks the transfer through to completion. |
| **Deal stage** | Where a Deal currently sits in its lifecycle. See [`../product/workflows/transfer-lifecycle.md`](../product/workflows/transfer-lifecycle.md) for the full stage list. |
| **Agent negotiation** | The stage where a mandated agent negotiates commission (with the buying club) and personal terms (with the player) in parallel. |
| **Personal terms** | The wage, signing bonus, and contract length proposed to the player; requires the player's consent to proceed. |
| **Medical check** | A staff-recorded pass/fail check on the player, tracked against the deal. |
| **Sell-on clause** | A percentage of a future resale fee owed back to a previous selling club. |
| **Instalment** | A scheduled partial payment of the agreed transfer fee. |

## Finance

| Term | Definition |
|---|---|
| **Transfer budget** | A club's total available funds for transfer fees. |
| **Reserved** | Funds provisionally held against an active bid/offer. |
| **Committed** | Funds locked in once a deal is agreed but not yet completed. |
| **Spent** | Funds actually paid out on a completed deal. |
| **Wage budget** | A club's total available weekly wage capacity, tracked in parallel to the transfer budget. |

## Related documents

- [`../product/workflows/transfer-lifecycle.md`](../product/workflows/transfer-lifecycle.md) — how these terms fit into the end-to-end flow
- [`../architecture/data-model.md`](../architecture/data-model.md) — how these concepts map to database entities
