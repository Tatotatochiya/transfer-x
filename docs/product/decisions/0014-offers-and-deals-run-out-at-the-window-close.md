---
title: "ADR 0014: Offers and Deals Run Out at the Buying Club's Window Close"
last_updated: 2026-11-28
status: Accepted
owner: "TODO — assign a Product Owner"
---

# ADR 0014: Offers and Deals Run Out at the Buying Club's Window Close

## Context

Before this decision, an offer expired seven days after it was sent unless the buyer chose a date. A deal never expired. Once paperwork was done, a deal had a 14-day completion target, and missing it only alerted both clubs. Under [ADR 0010](./0010-deals-run-all-year-windows-hold-completion.md), a deal that missed the window simply waited for the next one, however many months away. Clubs couldn't see from an offer or a deal how long it had left.

In practice a window close is a hard deadline. An agreement that hasn't gone through by deadline day is usually renegotiated, not carried over unchanged, because by then the player, the price and both squads will have changed.

## Decision

1. **The window that sets the date** is the buying club's: the club that registers the player, whose country's windows apply under ADR 0010. If that window is open, its close is the date. Between windows, the date is when the next window closes.
2. **Offers:** by default an offer expires at that date. With no windows set up for the buying club's country, an offer lasts seven days, as before. A buyer can still choose an earlier expiry when making the offer.
3. **Deals:** a deal between two clubs gets the same date when it is created.
   - **If not completed by then:** the deal collapses automatically, the buyer's committed budget is released, and the listing re-opens if there was one.
   - **Reason recorded:** the reason is recorded as "The transfer window closed before the deal completed".
   - **Warning:** both clubs are warned once, two days before (`DEAL_EXPIRING`).
   - **Exceptions:** free agents and pre-contracts don't wait for a window, so they don't expire.
   - **Job:** this is job `expire_deals`, which runs every five minutes.
4. **Deals from before this change:** a deal that was already open gets its date the first time the job runs. That date is always in the future, because it is the current window's close or the next one's.
5. **Where it shows:** the offer page and the deal page show the exact expiry time with a live countdown. Rows on the Transfers board show the time left and keep counting down.

This replaces part of ADR 0010. A closed window still holds completion. But a deal no longer waits for the next window: it collapses when its own window closes.

## Alternatives considered

- **Show the deadline, but let a missed deal wait for the next window (ADR 0010 as it was).** This is the gentler option. Nothing is lost automatically, but a deal agreed in August could sit open until January on terms nobody still holds.
- **Use the selling club's window.** The selling club doesn't register the player, so its window doesn't decide whether the transfer can go through.
- **Keep seven days for offers between windows.** Offers made between windows would then lapse long before any could complete, and clubs would have to remake them.

## Consequences

- **Deals agreed on deadline day can be lost.** A deal agreed close to the window's close collapses if completion doesn't happen in time. Real leagues allow a deal sheet to buy extra hours; that isn't modelled yet. Staff can still complete a deal with the Complete tool, or the clubs can agree again in the next window.
- **Collapse is automatic.** Budgets are released and listings re-open without anyone pressing a button, and the deal's timeline records why.
- **Admin-entered dates matter more.** A window entered late or wrongly now ends deals, not just completion. Admin → Transfer Windows' coverage warning should be acted on.
- **Code:** `transfer_window/service.window_close_for`, `deals/service.set_window_expiry` and `expire_deals`, and the offer default in `offers/service.create_offer`. Migration `0118` adds `deals.expires_at`, `deals.expiry_warned_at` and `DEAL_EXPIRING`.
