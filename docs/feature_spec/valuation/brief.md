---
title: "Valuation: the product owner's brief"
last_updated: 2026-11-13
status: Historical — the request of 2026-11-10 that the execution plan answers
owner: "TODO — assign a Product Owner"
---

# Valuation: the product owner's brief

## Purpose

The request that started the `market-v3` work, kept as written on 2026-11-10 apart from layout and spelling. The [execution plan](./execution-plan.md) answers it; the [execution log](./execution-log.md) records what was built.

## Background

TransferX is a football player transfer platform. The latest conversation about the requirement is in `conversation.jfif` (not in the repository). The goal is to explore how to make the player valuation more accurate by relying on a third-party platform that allows API access, so we don't run into legal problems down the line.

## What was understood at the time

**Valuations vs real fees**

- API-Football gives us each player's last transfer fee, but not a current market value.
- We already hold the fee for 309 of the 532 contracted players with a transfer on record (e.g. Rice ~£100m to Arsenal, Palmer ~£40m to Chelsea). We just don't show it yet.
- Plan:
  1. Show the last fee next to our value: "Last transfer: £100m (Jul 2023, West Ham → Arsenal)".
  2. Anchor our value to that fee, adjusted for time since, age, contract and form. This removes the obviously-off numbers.
  3. Let staff fill in missing fees by hand, with the source noted.
- No scraping. Transfermarkt and similar sites forbid it, and the data is legally protected. Not something to build a club-facing product on.
- Longer term: a licensed provider for live market values. Sportmonks is worth checking for coverage, cost and licence terms. The app already has a slot to plug one in.

**Order**

1. Anchoring valuations to last fees: tested against real fees first.
2. Sportmonks: needs a team decision on cost and terms. Sportmonks is a bit too expensive given we are a startup.

## The task

Based on what the project already has, create a detailed execution plan that a cheaper agent could follow. The plan should:

- include environment setup, so the code runs on the working machine;
- set out the best options available at this stage to improve player valuation and history, on top of what exists;
- give a detailed guide to what to implement and how, and how to test that it is delivered as intended;
- specify a user-friendly outcome test that shows the quality of the change with a few player examples, such as Haaland or Ronaldo, and some less famous players.

## Related

- [Execution plan](./execution-plan.md)
- [Market data and the last-fee anchor](./market-data.md): the design background
