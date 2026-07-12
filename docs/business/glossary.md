---
title: "Glossary"
last_updated: 2026-07-12
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
| **Club staff role** | The scoped role a non-owner club member holds: Sporting Director (deal authority + approvals), Manager (day-to-day market/deals), Scout (shortlists only), or Read-only (oversight). Each maps to a fixed capability set — see [`../architecture/authentication-and-permissions.md`](../architecture/authentication-and-permissions.md#club-roles). Distinct from platform (TransferX) staff. |
| **Invitation** | The owner-issued, emailed single-use link through which a new staff member joins a club and sets their own password. Expires after 7 days; can be revoked; the link is shown exactly once. |
| **Mandate** | The formal representation relationship between an agent and a player; can be exclusive or non-exclusive, and has a validity period. |

## Listings & bidding

| Term | Definition |
|---|---|
| **Sale** | A player listing created by a selling club. Has a type: **Auction**, **Fixed Price**, or **Open to Offers**. |
| **Bid** | An amount placed by a buying club against an auction-type Sale. |
| **Reserve price** | The minimum amount a seller will accept in an auction; visible only to the seller. |
| **Order book** | The ranked view of active bids/offers on a Sale. |
| **Transfer window** | An open/close date range within which clubs may transact, scoped to an **association** (a league/country/federation) or global. A club not covered by any configured window regime for its association is unregulated (open market). |
| **Fair value (model)** | TransferX's own performance-based estimate of a player's transfer value, with a confidence range. A deterministic formula over season box-score stats (`boxscore-v1`) — an estimate, never an official valuation. Not shown to player accounts. |
| **Divergence** | How far a reference price (asking price or agreed fee) sits from the model fair value, as a percentage with a band from "Well below model" to "Well above model". Never computed against a hidden reserve price. |

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
| **Medical check** | A pass/fail/waived check on the player, recorded by the **buying club** (or platform staff) against the deal. A failed medical blocks completion; the selling club cannot see the result — special-category personal data. |
| **Sell-on clause** | A percentage of a future resale fee owed back to a previous selling club. Triggering one creates a `RESALE`-type deal clause recording the obligation. |
| **Instalment** | A scheduled partial payment of the agreed transfer fee. |
| **Fee disclosure** | A per-deal choice (`fee_disclosed`) controlling whether the exact agreed fee appears on the public transfer feed, or is withheld. |

## Finance

| Term | Definition |
|---|---|
| **Transfer budget** | A club's total available funds for transfer fees. |
| **Approval threshold** | An optional per-club amount at or above which a Manager's money action (bid, offer, acceptance) waits as a pending approval for the owner or a Sporting Director to sign off, instead of executing. Nothing is reserved while pending; execution re-checks everything fresh. |
| **Reserved** | Funds provisionally held against an active bid/offer. |
| **Committed** | Funds locked in once a deal is agreed but not yet completed. |
| **Spent** | Funds actually paid out on a completed deal. |
| **Wage budget** | A club's total available weekly wage capacity, tracked in parallel to the transfer budget. |

## Related documents

- [`../product/workflows/transfer-lifecycle.md`](../product/workflows/transfer-lifecycle.md) — how these terms fit into the end-to-end flow
- [`../architecture/data-model.md`](../architecture/data-model.md) — how these concepts map to database entities
