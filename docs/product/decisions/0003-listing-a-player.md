---
title: "ADR 0003: A Player Is Listed Where He Is, as Open to Offers, With the Model as a Hint"
last_updated: 2026-09-25
status: Accepted
owner: "TODO — assign a Product Owner"
---

# ADR 0003: A Player Is Listed Where He Is, as Open to Offers, With the Model as a Hint

## Context

Listing a player was a full-page form (`/sales/new`) reached only from My Club's Listings tab or My Listings. The form did not know which player the club meant, so it was re-picked from a dropdown every time; it defaulted to Auction, which demands a deadline; and it ignored the model's fair-value estimate even though the pages that led to it had already loaded one. Measured before the change: 6 clicks plus typing from the squad, 7 from the player's own page, 5 from the listings page, and 3–5 more for an auction.

## Decision

1. **A club lists a player from wherever the player is**: a List action on his squad row, List for sale on his own page, and the listings pages. All three open the same form in a modal, and the club stays where it was afterwards. `/sales/new` remains for deep links; `?player_id=` preselects him.
2. **The default sale type is Open to Offers.** It is the listing that asks least of the seller (no price, no deadline), so the common case is two clicks from the squad row or the player page.
3. **The model's estimate is offered beside the price as a one-click "Use £X", never pre-filled**, and is not shown for auctions.
4. **The player-level `open_to_offers` flag and an Open to Offers listing stay separate concepts for now.** *(Superseded by [ADR 0005](./0005-one-listing-listed-means-available.md): the flag now means "has an open listing".)*

## Alternatives considered

- **Pre-fill the asking price with the model's figure.** Rejected: the model is an estimate, never a verdict (D5). Pre-filled, it becomes every listing's asking price unless the seller notices and changes it, which puts the model's number on the market without anyone having chosen it. One click to use it keeps the choice with the seller at almost no cost.
- **Default to Fixed Price or Auction.** Rejected: both need a figure or a date typed before the listing can exist, which is the friction this change removes.
- **Merge the `open_to_offers` flag into an Open to Offers listing.** Deferred, not rejected. The two overlap (both say "we would hear offers") but are not the same: the flag is a quiet signal on the player, while a listing is a public market entry that shows in Listings and can carry a price. Merging them changes the market's data model and the squad toggle, which is more than this change should carry.
- **A "+ List a player" picker in the Squad tab's header.** Dropped during the build: every squad row already has List, so a picker on the same screen would duplicate it. The picker lives on the Listings tab and My Listings.

## Consequences

- Clicks to list: squad row 2, player page 2, listings page 3 (was 6, 7 and 5, plus typing).
- A listing still cannot be edited: repricing means withdraw and relist. The modal is where the price gets confirmed.
- One-click listing made a latent gap real: nothing stopped a player being listed twice (a double-click, two tabs). A partial unique index now guarantees at most one open listing per player (migration `0070`), with a readable 409 from the router.
- Because of decision 4, the player page can show "Closed to offers" beside "View listing" for a player listed as Open to Offers. This is visible now and is the reason to revisit that decision.

## Related documents

- [`../workflows/negotiation-and-offers.md`](../workflows/negotiation-and-offers.md) — how listing works
- [`../../CHANGELOG.md`](../../CHANGELOG.md) — the change entry
