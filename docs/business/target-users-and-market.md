---
title: "Target Users & Market"
last_updated: 2026-07-03
status: Draft
owner: "TODO — assign a Business/Product Owner"
---

# Target Users & Market

## Purpose

Defines who TransferX is for commercially — which market segment(s) it targets and why. This is the business framing of "who"; the product-level framing (what each user type needs from the product) lives in [`../product/personas.md`](../product/personas.md).

## Scope

In scope: target market segment(s), buyer vs. user distinction, market sizing and competitive framing.
Out of scope: individual user needs and journeys (see [`../product/personas.md`](../product/personas.md) and [`../product/workflows/`](../product/workflows/README.md)).

## Table of Contents

- [User types supported today](#user-types-supported-today)
- [Target market segment](#target-market-segment)
- [Competitive landscape](#competitive-landscape)
- [Related documents](#related-documents)

## User types supported today

The platform currently has first-class support for four account types (verified in the codebase's `UserType` model):

| Type | Role |
|---|---|
| Club | Buys and/or sells players; role is configurable (buyer / seller / both) |
| Agent | Represents players; negotiates commission and personal terms on their behalf |
| Player | Manages their own profile, visibility, and consent to personal terms |
| Staff | Club employee with scoped access to a club's account |
| Admin | Platform-level superuser |

This is a factual list of what the software supports today, not a statement of market priority — see below.

## Target market segment

> **TODO:** Which tier of club is TransferX built for? (e.g. professional leagues such as Premier League/Championship/European clubs, vs. lower-league/semi-pro clubs.) This is a real open decision, not yet settled in the documentation.
>
> Historical planning notes point in different directions at different points in the project's history — this needs a single, current, owned answer rather than an inferred one.

## Competitive landscape

> **TODO:** Who are the comparable products/competitors, and how does TransferX intend to differentiate? (e.g. existing transfer-market platforms, scouting tools, agent CRM tools.)

## Related documents

- [`../product/personas.md`](../product/personas.md) — product-level detail on each user type
- [`business-model.md`](./business-model.md) — how different segments translate to revenue
- [`vision.md`](./vision.md) — the problem this market segment has
