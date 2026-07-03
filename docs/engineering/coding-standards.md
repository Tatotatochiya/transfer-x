---
title: "Coding Standards"
last_updated: 2026-07-03
status: Draft
owner: "TODO — assign a Technical Lead"
---

# Coding Standards

## Purpose

Conventions and style rules for contributing code to TransferX — both backend and frontend.

## Scope

In scope: code style, structural conventions, naming, and patterns specific to this codebase.
Out of scope: testing approach (see [`testing-strategy.md`](./testing-strategy.md)), architectural boundaries (see [`../architecture/README.md`](../architecture/README.md)).

## Table of Contents

- [Backend conventions](#backend-conventions)
- [Frontend conventions](#frontend-conventions)
- [General](#general)
- [Related documents](#related-documents)

## Backend conventions

- Each domain module follows a `models.py` / `schemas.py` / `service.py` / `router.py` layering (see [`../architecture/backend-architecture.md`](../architecture/backend-architecture.md)).

> **TODO:** Document linting/formatting tools in use (if any — a `.ruff_cache` exists in the repo, suggesting Ruff), type-checking conventions, and any project-specific patterns worth calling out (e.g. concurrency-safe patterns for money-affecting operations).

## Frontend conventions

- TanStack Query for server state, Zustand for client state (see [`../architecture/frontend-architecture.md`](../architecture/frontend-architecture.md)).

> **TODO:** Document component conventions, TypeScript strictness, and formatting tools in use.

## General

> **TODO:** Document commit message conventions, branch naming, and PR expectations, if/when formalized.

## Related documents

- [`../architecture/backend-architecture.md`](../architecture/backend-architecture.md) — the structure these standards apply to
- [`../architecture/frontend-architecture.md`](../architecture/frontend-architecture.md) — the structure these standards apply to
- [`testing-strategy.md`](./testing-strategy.md) — how changes following these standards get verified
