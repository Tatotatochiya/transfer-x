---
title: "Getting Started"
last_updated: 2026-07-03
status: Active
owner: "TODO — assign a Technical Lead"
---

# Getting Started

## Purpose

How to get TransferX running locally. The step-by-step commands are maintained once, in the repository root `README.md`, and linked from here rather than duplicated — see [Rationale](#rationale).

## Scope

In scope: pointers to local setup instructions and a summary of the pieces involved.
Out of scope: production deployment (see [`../operations/environments-and-deployment.md`](../operations/environments-and-deployment.md)).

## Table of Contents

- [Quick start](#quick-start)
- [Services](#services)
- [Rationale](#rationale)
- [Related documents](#related-documents)

## Quick start

See the repository root [`README.md`](../../README.md) for exact, current commands (Docker Compose for the full stack, or running backend/frontend independently).

> **TODO:** If the root `README.md` setup steps and this document ever diverge, treat the root `README.md` as authoritative for "how do I run this" and fix this document to match, or migrate the content here fully and have the root `README.md` link back — pick one direction rather than letting both drift independently.

## Services

| Service | Local URL |
|---|---|
| Frontend | `http://localhost:5173` |
| Backend API | `http://localhost:8001` |
| API docs (Swagger) | `http://localhost:8001/docs` |
| PostgreSQL | `localhost:5432` |

## Rationale

Setup commands are exactly the kind of fact that goes stale fast if written in two places. Keeping them in one file (the root `README.md`, which is also what a new contributor finds first when they open the repository) and linking to it satisfies this documentation set's goal of avoiding duplicate information.

## Related documents

- [`../../README.md`](../../README.md) — repository root README with exact setup commands
- [`../architecture/system-overview.md`](../architecture/system-overview.md) — what these services are and how they relate
- [`coding-standards.md`](./coding-standards.md) — conventions to follow once your environment is running
