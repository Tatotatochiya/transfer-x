---
title: "Engineering Documentation — Overview"
last_updated: 2026-07-03
status: Active
owner: "TODO — assign a Technical Lead"
---

# Engineering Documentation

## Purpose

This area answers **how to work in this codebase day to day** — setup, standards, testing, migrations, and API reference. It documents *process*, not system design (see [`../architecture/`](../architecture/README.md) for that).

## Scope

In scope: local environment setup, coding conventions, testing approach, database migration workflow, and where to find API reference material.
Out of scope: system/module design (see [`../architecture/`](../architecture/README.md)), production operations (see [`../operations/`](../operations/README.md)).

## Table of Contents

| Document | Purpose |
|---|---|
| [`getting-started.md`](./getting-started.md) | Local environment setup |
| [`coding-standards.md`](./coding-standards.md) | Conventions and style |
| [`testing-strategy.md`](./testing-strategy.md) | How testing works and what's covered |
| [`database-migrations.md`](./database-migrations.md) | Alembic migration workflow |
| [`api-reference.md`](./api-reference.md) | Where the API reference lives |

## Related Documents

- [`../PRODUCT_SPEC.md`](../PRODUCT_SPEC.md) — master index
- [`../architecture/README.md`](../architecture/README.md) — the system design this process operates on
- [`../operations/README.md`](../operations/README.md) — running the result of this work in production
