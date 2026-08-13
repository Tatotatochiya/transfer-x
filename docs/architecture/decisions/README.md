---
title: "Architecture Decision Records"
last_updated: 2026-08-13
status: Active
owner: "TODO — assign a Technical Lead"
---

# Architecture Decision Records (ADRs)

## Purpose

A record of significant, hard-to-reverse technical decisions — what was decided, the alternatives considered, and why. The goal is that a later contributor (human or AI) can understand *why* the system looks the way it does, not just *that* it does.

## Scope

In scope: system-design decisions (e.g. choice of database, a module boundary, a stage-machine redesign). For product-level decisions (what to build, not how), see [`../../product/decisions/README.md`](../../product/decisions/README.md) instead.

## Table of Contents

- [0001 — Vendor-sourced data never overrides an active TransferX contract](./0001-vendor-data-never-overrides-transferx-contract.md)
- [0002 — Contract-cliff value-at-risk prefers the fair-value model over legacy market value](./0002-contract-cliff-prefers-fair-value-over-legacy-market-value.md)
- [0003 — Player status distinguishes external clubs from free agency](./0003-player-status-distinguishes-external-clubs.md)
- [0004 — An anonymous buyer is masked server-side, not hidden in the UI](./0004-anonymous-buyer-masked-server-side.md)

> **TODO:** Add further decisions here as `NNNN-short-title.md`, following the short template: Context, Decision, Alternatives considered, Consequences. Link it from this table.
>
> Other good candidates for a retroactive ADR: the deal-stage machine design (why `AGENT_NEGOTIATION` sits where it does), or the choice to model club finance as reserved/committed/spent rather than a simpler balance.

## Related Documents

- [`../README.md`](../README.md) — architecture documentation overview
- [`../../product/decisions/README.md`](../../product/decisions/README.md) — the product-level equivalent of this log
