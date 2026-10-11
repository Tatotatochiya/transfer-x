---
title: "Personas"
last_updated: 2026-10-11
status: Draft
owner: "TODO — assign a Product Owner"
---

# Personas

## Purpose

Describes who uses TransferX and what role they play in the product. This is the product-level companion to [`../business/target-users-and-market.md`](../business/target-users-and-market.md), which covers the commercial/market framing of the same user types.

## Scope

In scope: the account types the product supports today, and (once filled in) their goals, pain points, and what they need from the product.
Out of scope: commercial segmentation and market sizing (see [`../business/target-users-and-market.md`](../business/target-users-and-market.md)).

## Table of Contents

- [Selling Club](#selling-club)
- [Buying Club](#buying-club)
- [Club Staff](#club-staff)
- [Agent](#agent)
- [Player](#player)
- [Platform Admin](#platform-admin)
- [Related documents](#related-documents)

Each persona below is grounded in an account type that exists in the product today (see [`../architecture/authentication-and-permissions.md`](../architecture/authentication-and-permissions.md)). The "who they are" facts are verified against the code; the "goals / needs / pain points" sections are placeholders pending real product research.

## Selling Club

**Who they are:** A club account listing players for transfer, receiving and responding to bids/offers, and progressing agreed deals.

> **TODO:** Goals, needs, and pain points — requires input from real or representative selling-club users (e.g. a Sporting Director or recruitment lead).

## Buying Club

**Who they are:** A club account browsing the market, placing bids/offers, and progressing agreed deals through to completion.

> **TODO:** Goals, needs, and pain points.

## Club Staff

**Who they are:** People at a club who are not the club's primary account holder — invited by the owner with one of four roles, each mapping to what that person actually does: **Sporting Director** (deal authority, club admin, decides spending approvals), **Manager** (runs the market and deals day to day; large spends can require approval), **Scout** (shortlists and market views, no bidding), **Read-only** (board member/CEO oversight — sees everything, changes nothing). A director can switch to **Lite mode**: a big-type interface for deciding on offers, approvals and bids, with a 10-second undo. Distinct from [Platform Admin](#platform-admin): "club staff" work *for a club*; platform admins work *for TransferX*.

> **TODO:** Goals, needs, and pain points per staff role.

## Agent

**Who they are:** Represents one or more players under a mandate. Can negotiate commission with a buying club and personal terms with the player in parallel once a deal reaches the agent-negotiation stage.

> **TODO:** Goals, needs, and pain points.

## Player

**Who they are:** A player joins only by invitation from the club that holds his contract, or, as a free agent, from TransferX staff or his agent (product ADR 0007). With an account he sees his profile and answers personal terms. His mandated agent can answer for him too. Whether he's available is his club's call, through a listing.

> **TODO:** Goals, needs, and pain points.

## Platform Admin

**Who they are:** TransferX staff (superusers). They start on the admin panel and invite clubs. They oversee every entity, settle disputes such as a contested loan obligation, decide verification requests, and run transfer windows and data syncs. They watch Jobs, Errors and Health. Every change they make is audited with a reason, and they can view a club read-only.

> **TODO:** Goals, needs, and pain points.

## Related documents

- [`../business/target-users-and-market.md`](../business/target-users-and-market.md) — the commercial framing of these same user types
- [`workflows/README.md`](./workflows/README.md) — the journeys these personas move through
- [`../architecture/authentication-and-permissions.md`](../architecture/authentication-and-permissions.md) — how these roles are technically implemented
