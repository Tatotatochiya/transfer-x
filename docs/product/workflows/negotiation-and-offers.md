---
title: "Workflow: Negotiation & Offers"
last_updated: 2026-11-08
status: Draft
owner: "TODO — assign a Product Owner"
---

# Workflow: Negotiation & Offers

## Purpose

Describes how a listing attracts interest and how that interest becomes an agreed deal, through offers and negotiation. Auctions are retired ([product ADR 0011](../decisions/0011-auctions-retired.md)).

## Scope

In scope: sale/listing types, bidding mechanics, offer/counter-offer mechanics, and how either resolves into a Deal.
Out of scope: what happens after a deal exists (see [`transfer-lifecycle.md`](./transfer-lifecycle.md)).

## Table of Contents

- [Listing types](#listing-types)
- [Listing a player](#listing-a-player)
- [Before an offer: enquiries](#before-an-offer-enquiries)
- [Direct offer flow](#direct-offer-flow)
- [Diagram](#diagram)
- [Related documents](#related-documents)

## Listing types

A listing means "available" ([product ADR 0005](../decisions/0005-one-listing-listed-means-available.md)): a player is open to offers exactly when he has an open listing. A listing can be for transfer, loan or either ([ADR 0004](../decisions/0004-listing-availability-transfer-loan-or-either.md)).

| Type | Mechanic |
|---|---|
| **Open to Offers** (every new listing) | An optional guide price and an optional "Offers by" date; buying clubs make offers and the seller chooses |
| **Fixed Price** | No longer offered in the UI; existing fixed-price listings still work |
| **Auction** | Retired 2026-11-08 ([ADR 0011](../decisions/0011-auctions-retired.md)). `POST /sales` refuses it; past auctions and their deals stay as history |

The "Offers by" date is the "best offers by Friday" a club sets when several want a player: clubs see it, and the listing expires then (`close_expired_sales`). Offers already made run to their own expiry and can still be answered.

## Listing a player

Only the club that owns a player can list him. A player on loan *to* a club is registered there, but his parent club owns him and is the one that can sell him (see [ADR 0005](../../architecture/decisions/0005-loan-registration-separate-from-ownership.md)). He cannot be listed while a transfer deal for him is in progress. Since 2026-11-07 a closed transfer window doesn't stop listing or offers; it holds only completion ([product ADR 0010](../decisions/0010-deals-run-all-year-windows-hold-completion.md)).

A club lists a player from wherever he is: **List** on his squad row, **List for sale** on his own page, or the listings pages, which open the same form with a squad picker. The picker disables players who cannot be listed and says why. `/sales/new?player_id=` opens the form as a page, for deep links. Once a player is listed, his row shows **Listed →** and his page shows **View listing**, both linking to the listing.

- **Defaults:** Open to Offers, no price, no "Offers by" date.
- **The model's estimate** appears beside the price as a one-click suggestion. It is never pre-filled. The reasons are in [product ADR 0003](../decisions/0003-listing-a-player.md).
- **A player has at most one open listing**, enforced by the database. A listing cannot be edited: to change its price or type, withdraw it and list again.

## Before an offer: enquiries

A club can ask about any TransferX player before making an offer: openly, or anonymously as "A {league} club". There's one open enquiry per club per player. Either side replies or closes it, and it shows as "your move" on the dashboard and board.

## Direct offer flow

1. **Offer.** The buying club offers on a player at a TransferX club, listed or not. It can be permanent or loan, open or anonymous. It carries the fee, or a £0 fee with a reason, plus the wage, the payment schedule, add-ons, sell-on, any loan terms and an expiry.
   - The fee and wage are reserved against the buyer's budget.
   - Above the club's approval threshold, the offer waits for the owner or sporting director to approve it.
   - Players at clubs outside TransferX can't be offered for.
2. **Responses.** The seller accepts, rejects or counters. A counter can change any term except the deal type, and is validated like a new offer. Either side can keep countering, and the buyer can improve its own offer or withdraw it.
3. **Expiry.** An offer past its expiry is closed by the `expire_stale_offers` job, and the reservation is released.
4. **Acceptance.** The terms are copied onto a new deal ([transfer lifecycle](./transfer-lifecycle.md)). Rival buyers' offers on the same player are closed and their reservations released, and an anonymous buyer is revealed to the seller. The offer page then sends both clubs to the deal.

The whole conversation for a transfer (enquiry, offer messages, deal room) reads as one thread on the board ([architecture ADR 0008](../../architecture/decisions/0008-one-conversation-read-across-existing-messages.md)).

## Diagram

```mermaid
sequenceDiagram
    participant B as Buying club
    participant T as TransferX
    participant S as Selling club
    B->>T: Offer (budget reserved; approval if above threshold)
    T->>S: Offer received (your move)
    S->>T: Counter
    T->>B: Counter received (your move)
    B->>T: Improve / accept counter
    S->>T: Accept
    T->>T: Create deal, release rivals' reservations
    T-->>B: Deal created
    T-->>S: Deal created
```

## Related documents

- [`transfer-lifecycle.md`](./transfer-lifecycle.md) — what happens once a bid/offer is accepted
- [`../../business/glossary.md`](../../business/glossary.md) — definitions of Sale, Bid, Offer, Order book
