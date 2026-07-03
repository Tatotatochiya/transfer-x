---
title: "Architecture Documentation — Overview"
last_updated: 2026-07-03
status: Active
owner: "TODO — assign a Technical Lead"
---

# Architecture Documentation

## Purpose

This area answers **how TransferX is designed as a system** — the stack, module boundaries, data model, and cross-cutting concerns like authentication. It documents *structure*, not day-to-day development process (see [`../engineering/`](../engineering/README.md) for that).

## Scope

In scope: system design, module/component boundaries, data model, and records of significant architectural decisions.
Out of scope: local dev setup and workflow (see [`../engineering/`](../engineering/README.md)), production operations (see [`../operations/`](../operations/README.md)), what to build and why (see [`../product/`](../product/README.md)).

## Table of Contents

| Document | Purpose |
|---|---|
| [`system-overview.md`](./system-overview.md) | High-level stack and how the pieces fit together |
| [`backend-architecture.md`](./backend-architecture.md) | FastAPI module layout |
| [`frontend-architecture.md`](./frontend-architecture.md) | React application structure |
| [`data-model.md`](./data-model.md) | Core entities and their relationships |
| [`authentication-and-permissions.md`](./authentication-and-permissions.md) | How auth/authorization is implemented |
| [`decisions/`](./decisions/README.md) | Architecture decision records (ADRs) |

## Related Documents

- [`../PRODUCT_SPEC.md`](../PRODUCT_SPEC.md) — master index
- [`../engineering/README.md`](../engineering/README.md) — how to actually work in this codebase
- [`../security-and-compliance/permissions-model.md`](../security-and-compliance/permissions-model.md) — the *risk posture* of the auth model described here (distinct scope — see that document for the split)
