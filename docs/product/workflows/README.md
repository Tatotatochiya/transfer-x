---
title: "Workflows — Overview"
last_updated: 2026-07-03
status: Active
owner: "TODO — assign a Product Owner"
---

# Workflows

## Purpose

Describes TransferX's core user journeys at the level a product manager or new team member should understand them — sequence of steps, who's involved, what decisions get made. This is **not** an API or code reference; see [`../../architecture/backend-architecture.md`](../../architecture/backend-architecture.md) for implementation.

## Scope

In scope: end-to-end journeys spanning multiple user types and product areas.
Out of scope: implementation detail (routes, database tables, function names) — link to `architecture/` for that instead of duplicating it here.

## Table of Contents

| Document | Covers |
|---|---|
| [`transfer-lifecycle.md`](./transfer-lifecycle.md) | The full deal lifecycle from listing to completion |
| [`negotiation-and-offers.md`](./negotiation-and-offers.md) | How bids and offers are placed, countered, and resolved |
| [`agent-representation.md`](./agent-representation.md) | How an agent's mandate and negotiation fit into a deal |
| [`deal-completion.md`](./deal-completion.md) | The staged approval process from agreement to a completed transfer |

## Related Documents

- [`../README.md`](../README.md) — product documentation overview
- [`../personas.md`](../personas.md) — who moves through these workflows
- [`../../architecture/data-model.md`](../../architecture/data-model.md) — the entities these workflows operate on
