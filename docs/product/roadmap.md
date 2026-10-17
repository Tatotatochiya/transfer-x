---
title: "Roadmap"
last_updated: 2026-10-11
status: Active
owner: "TODO — assign a Product Owner"
---

# Roadmap

## Purpose

Gives the phased, narrative view of where TransferX is headed. The **detailed, day-to-day backlog is not duplicated here** — it lives in Linear (project: TransferX) and should be treated as the source of truth for ticket-level status.

## Scope

In scope: phase-level plan, what each phase is trying to achieve, and pointers to the live backlog.
Out of scope: individual ticket detail (Linear), technical implementation plans (see [`../architecture/decisions/`](../architecture/decisions/README.md)).

## Table of Contents

- [How to read this document](#how-to-read-this-document)
- [Current phases](#current-phases)
- [Related documents](#related-documents)

## How to read this document

This is a narrative summary, refreshed periodically. For current, authoritative status of any specific piece of work, check Linear directly rather than trusting this document's detail — only the phase names and goals below should be considered durable.

## Current phases

**The current plan is [`../feature_spec/phased-plan-2026-q4/README.md`](../feature_spec/phased-plan-2026-q4/README.md)** (from the 3 October 2026 review). Where it stood on 2026-10-11:

| Phase | Goal | Status |
|---|---|---|
| 0. Ship what's in flight | Everything built reaches Railway and real phones | Done except the real-phone notification test |
| 1. Trust basics | Nothing a club's finance or legal team would reject | Done except two-factor sign-in (deferred) |
| 2. Compliance and completion | Registration (TMS, ITC, permits), windows by federation, a real medical, deadline day | Started: deadline-day mode built 2026-10-17 |
| 3. Simplify the core | One board, one conversation, one way to buy | Done |
| 4. Money and documents | Full personal terms, cost per season, payments that reconcile, e-signatures | Not started |
| 5. Planning, agents and players | Squad lists and quotas, renewals, agent tools, a player view | Not started |

**Built alongside the plan:**
- the AI analyst (Ask TransferX, phases A and B);
- valuation model v2 (calibration still to do);
- the scheduled data refresh with Admin Jobs and Errors.

These are in [`../IMPLEMENTATION_STATUS.md`](../IMPLEMENTATION_STATUS.md).

**Decisions still needed** (from the plan):
- the business model;
- a pilot with 2–3 clubs;
- data sources (Transfermarkt licence, API-Football coverage).

Linear (project TransferX) was organised into Marketplace Core, Agent Experience, Differentiation & Demo Readiness, and Production & Business Readiness. The phased plan supersedes that structure for ordering work.

> **TODO:** No target dates exist. Add a coarse view (by quarter) once the team commits to one.

## Related documents

- [`personas.md`](./personas.md) — who each phase is ultimately serving
- [`workflows/README.md`](./workflows/README.md) — the user journeys this roadmap is building toward
- [`../business/vision.md`](../business/vision.md) — the underlying problem this roadmap works toward solving
