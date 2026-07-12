---
title: "Architecture Decision Records"
last_updated: 2026-07-12
status: Active
owner: "TODO — assign a Technical Lead"
---

# Architecture Decision Records (ADRs)

## Purpose

A record of significant, hard-to-reverse technical decisions — what was decided, the alternatives considered, and why. The goal is that a later contributor (human or AI) can understand *why* the system looks the way it does, not just *that* it does.

## Scope

In scope: system-design decisions (e.g. choice of database, a module boundary, a stage-machine redesign). For product-level decisions (what to build, not how), see [`../../product/decisions/README.md`](../../product/decisions/README.md) instead.

## Table of Contents

- [0001 — Staff override endpoints bypass the ordinary completion gates](./0001-staff-overrides-bypass-completion-gates.md)

> **TODO:** Add further decisions here as `NNNN-short-title.md`, following the short template: Context, Decision, Alternatives considered, Consequences. Link it from this table.
>
> Good candidates for a future ADR: the deal-stage machine design (why `AGENT_NEGOTIATION` sits where it does), or the choice to model club finance as reserved/committed/spent rather than a simpler balance.

## Related Documents

- [`../README.md`](../README.md) — architecture documentation overview
- [`../../product/decisions/README.md`](../../product/decisions/README.md) — the product-level equivalent of this log
