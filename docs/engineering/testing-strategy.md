---
title: "Testing Strategy"
last_updated: 2026-07-03
status: Draft
owner: "TODO — assign a Technical Lead"
---

# Testing Strategy

## Purpose

Describes how testing works in TransferX and what's currently covered.

## Scope

In scope: test frameworks in use, how to run tests, and current coverage state.
Out of scope: CI/CD pipeline configuration (see [`../operations/`](../operations/README.md) once one exists).

## Table of Contents

- [Backend testing](#backend-testing)
- [Frontend testing](#frontend-testing)
- [Current coverage](#current-coverage)
- [Related documents](#related-documents)

## Backend testing

Pytest. Test files live under `backend/tests/`.

> **TODO:** Document test database strategy (e.g. SQLite vs. Postgres for tests), fixtures conventions, and how to run a single test vs. the full suite.

## Frontend testing

Vitest + Testing Library + MSW (for API mocking). Test files live alongside components as `*.test.tsx` / `*.test.ts`.

> **TODO:** Document conventions for what should be unit-tested vs. left to manual verification.

## Current coverage

As a rough, point-in-time indicator (verify before relying on this): 19 backend test files, 6 frontend test files.

> **TODO:** This is not a coverage percentage and shouldn't be read as one — replace with real coverage tooling output if/when that's set up.

## Related documents

- [`coding-standards.md`](./coding-standards.md) — conventions the tests should enforce
- [`../architecture/README.md`](../architecture/README.md) — the system these tests verify
