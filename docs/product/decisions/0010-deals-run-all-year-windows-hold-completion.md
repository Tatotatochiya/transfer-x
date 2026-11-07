---
title: "ADR 0010: Deals Run All Year; a Country's Transfer Window Holds Only Completion"
last_updated: 2026-11-07
status: Accepted
owner: "TODO — assign a Product Owner"
---

# ADR 0010: Deals Run All Year; a Country's Transfer Window Holds Only Completion

## Context

Until 2026-11-07 a configured transfer window blocked offers, listings, Lite bids and direct signings outside it, while a deal agreed inside a window could complete at any time. Real football works the other way round. Clubs talk, bid and agree fees all year; deals agreed in spring "go through when the window opens". What a window controls is **registration**: a player can't be registered at his new club until it opens. An unattached player can be registered outside a window in most leagues, including the Premier League.

Windows were also global: one set of dates for every club. In reality each FIFA member association sets its own two registration periods a season, and a window governs only transfers *into* that country. The Premier League's summer window closes on 1 September, others later; Scandinavian leagues run on a calendar-year season.

There is no official feed of window dates. FIFA publishes every association's dates in its registration period calendar (inside.fifa.com, kept by the associations), but as a web page, with no API. API-Football and Sportmonks have transfer records, not window dates.

## Decision

1. **Offers, listings, bids, enquiries and direct signings are allowed all year.** The window checks on `POST /offers`, `POST /sales`, approvals, Lite bids and the direct-signing endpoints are gone.
2. **A transfer between two clubs completes only while the buying club's window is open.** CONFIRMED → COMPLETED is refused with "The transfer window in {country} is closed. The deal can complete when the {name} window opens on {date}." Talks and paperwork carry on. Both clubs see this on the deal page, and both are told when the window opens (job `window_opened`). Waiting for the window doesn't count against the deal's completion deadline: the deadline restarts from the opening. The staff Complete tool overrides it, with a reason.
3. **Free agents and pre-contracts don't wait.** An out-of-contract player can be registered at any time. Loans between clubs wait like transfers. A loan ending was never window-gated.
4. **Each window names a country.** A club follows its own country's windows, or, when its country has none, the windows with no country. With no windows at all, the market is open and nothing waits.
5. **Admins enter the dates, with a source.** Each window records where the dates came from (a link, usually FIFA's calendar or the league's announcement) and when they were checked. Admin → Transfer Windows lists every country with clubs on TransferX and warns when one has nothing open or set up for the next six months.

## Alternatives considered

- **Keep blocking offers outside the window.** Simpler, but it stops exactly what clubs do between windows, and let deals agreed in a window complete months later.
- **Scrape FIFA's calendar, or buy a feed.** No API exists. Scraping a page meant for people would break without warning, on a rule that decides whether a transfer can complete. Two windows a year per country is about five minutes of admin work.
- **Auto-complete held deals when the window opens.** Completion moves money and the player's contract, so the clubs do it, as they do in any window. They're told it's ready.

## Consequences

- Deadline day still matters: a deal not completed before the window closes waits for the next one. Deadline mode and its reminders follow each club's own country's window.
- `Club.country` decides which windows apply. A club with no country follows the windows with no country.
- Registration-period exceptions beyond free agents (emergency goalkeeper signings, league-specific rules) aren't modelled. Staff can complete such a deal with the Complete tool and a reason.
- Code: `backend/app/transfer_window/service.py` (`windows_for`, `completion_hold`, `coverage`, `notify_opened_windows`); migration `0108`.
