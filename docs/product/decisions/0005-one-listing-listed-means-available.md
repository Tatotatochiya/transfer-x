---
title: "ADR 0005: One Kind of Listing, and Listed Means Available"
last_updated: 2026-09-27
status: Accepted
owner: "TODO — assign a Product Owner"
---

# ADR 0005: One Kind of Listing, and Listed Means Available

## Context

A club had three ways to say "we would sell him":
- the player-level `open_to_offers` switch on the squad;
- an Open to Offers listing;
- a Fixed Price listing.

The listing modal also offered Auction as a peer of the other two. A buying club saw "open to offers" badges on players with no listing, and listings with no badge. The two could not be told apart, and neither could be acted on the same way. [ADR 0004](./0004-listing-availability-transfer-loan-or-either.md) deferred merging the switch into the listing. This ADR does that.

## Decision

1. **The listing modal creates one kind of listing:** the club hears offers, optionally around a guide price and until a date.
   - An auction is still available, as an "Advanced" option for transfer listings only.
   - The modal no longer offers Fixed Price. Fixed-price listings that already exist keep working, and the API still accepts the type.
2. **A deadline is optional on any listing, not only auctions.**
   - A listing whose deadline has passed closes by itself: the hourly expiry job now covers every open listing.
   - A deadline in the past is refused.
3. **`open_to_offers` now means "has an open listing".**
   - For a player at a club, the flag is derived: `sync_listed_flag` sets it whenever a listing opens or closes, whatever the path (create, withdraw, bid accepted, offer accepted, expiry, deal collapse reopening the listing, admin cancel).
   - The squad switch is gone, replaced by **Unlist**. Setting the flag directly returns 400: clubs make a player available by listing him.
   - Migration `0078` backfills the flag from listing state.
   - **Free agents keep their own switch,** because they have no club to list them.
4. **Every reader of the flag stayed unchanged:** market filter, badges, AI search and alerts. The UI now labels it "Listed".

## Consequences

- One answer to "is he available", and it is the one a buyer can act on (a listing with an order book).
- A club that liked the quiet, unlisted "we'd listen" signal loses it. **Enquiries** replace it: any club can ask about any TransferX player, openly or anonymously, without anyone listing anything.
- `open_to_offers` stays a stored column rather than a query. This is cheaper for the market filter, but it must stay in sync: any new code that opens or closes a listing has to call `sync_listed_flag`.

## Alternatives considered

- **Drop the column and compute it in every query.** It is the cleanest option, but it touches every market query, the AI search and the alerts. Deferred.
- **Keep Fixed Price in the modal.** In practice a fixed price was an open-to-offers listing with a guide price that clubs negotiated against anyway, and it confused which one to choose.
