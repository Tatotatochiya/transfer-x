---
title: "Workflow: Negotiation & Offers"
last_updated: 2026-10-11
status: Draft
owner: "TODO — assign a Product Owner"
---

# Workflow: Negotiation & Offers

## Purpose

Describes how a listing attracts interest and how that interest becomes an agreed deal — auctions (bidding) and direct offers (negotiation).

## Scope

In scope: sale/listing types, bidding mechanics, offer/counter-offer mechanics, and how either resolves into a Deal.
Out of scope: what happens after a deal exists (see [`transfer-lifecycle.md`](./transfer-lifecycle.md)).

## Table of Contents

- [Listing types](#listing-types)
- [Listing a player](#listing-a-player)
- [Before an offer: enquiries](#before-an-offer-enquiries)
- [Auction / bidding flow](#auction--bidding-flow)
- [Direct offer flow](#direct-offer-flow)
- [Diagram](#diagram)
- [Related documents](#related-documents)

## Listing types

A listing means "available" ([product ADR 0005](../decisions/0005-one-listing-listed-means-available.md)): a player is open to offers exactly when he has an open listing. A listing can be for transfer, loan or either ([ADR 0004](../decisions/0004-listing-availability-transfer-loan-or-either.md)).

| Type | Mechanic |
|---|---|
| **Open to Offers** (the default) | An optional guide price and deadline; buying clubs make offers |
| **Auction** (under "Advanced") | Buying clubs bid; the seller can accept the best bid above any reserve, or the auction closes at its deadline |
| **Fixed Price** | No longer offered in the UI; existing fixed-price listings still work |

Any listing's deadline expires it. Anti-sniping settings exist in the config but aren't used.

## Listing a player

Only the club that owns a player can list him. A player on loan *to* a club is registered there, but his parent club owns him and is the one that can sell him (see [ADR 0005](../../architecture/decisions/0005-loan-registration-separate-from-ownership.md)). He cannot be listed while a transfer deal for him is in progress, or outside a transfer window when windows are configured.

A club lists a player from wherever he is: **List** on his squad row, **List for sale** on his own page, or the listings pages, which open the same form with a squad picker. The picker disables players who cannot be listed and says why. `/sales/new?player_id=` opens the form as a page, for deep links. Once a player is listed, his row shows **Listed →** and his page shows **View listing**, both linking to the listing.

- **Defaults:** Open to Offers, no price. Auction fields (reserve, minimum bid increment, and a deadline defaulted a week out) appear only for an auction.
- **The model's estimate** appears beside the price as a one-click suggestion. It is never pre-filled and is not shown for auctions. The reasons are in [product ADR 0003](../decisions/0003-listing-a-player.md).
- **A player has at most one open listing**, enforced by the database. A listing cannot be edited: to change its price or type, withdraw it and list again.

## Before an offer: enquiries

A club can ask about any TransferX player before making an offer: openly, or anonymously as "A {league} club". There's one open enquiry per club per player. Either side replies or closes it, and it shows as "your move" on the dashboard and board.

## Auction / bidding flow

- **Buying club:** places a bid at or above the minimum next bid. Its budget is reserved for the bid, and released if it's outbid. It sees the order book without other clubs' identities.
- **Selling club:** sees every bid and accepts one, with a confirmation. Accepting creates a deal the clubs run themselves, like any other, and releases the other bidders' reservations.
- **Deadline:** an unaccepted auction closes at its deadline (the `close_expired_sales` job).

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
