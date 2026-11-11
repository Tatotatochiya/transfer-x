---
title: "Getting Started"
last_updated: 2026-11-11
status: Active
owner: "TODO — assign a Technical Lead"
---

# Getting Started

## Purpose

How to get TransferX running locally. The step-by-step commands are maintained once, in [`STARTER.md`](../../STARTER.md) at the repository root, and linked from here rather than duplicated — see [Rationale](#rationale).

## Scope

In scope: pointers to local setup instructions and a summary of the pieces involved.
Out of scope: production deployment (see [`../operations/environments-and-deployment.md`](../operations/environments-and-deployment.md)).

## Table of Contents

- [Quick start](#quick-start)
- [Services](#services)
- [Rationale](#rationale)
- [Related documents](#related-documents)

## Quick start

Follow [`STARTER.md`](../../STARTER.md): `.env` from `.env.example`, restoring the reference
snapshot (`backend/seeds/transferx_reference_20260808.dump`) into the empty database, starting the
stack (the API migrates on start), onboarding the Premier League clubs, the demo deals, a staff
account, the optional API-Football backfills, everyday commands and troubleshooting. The root
`README.md` keeps a short version and links there.

## Services

| Service | Local URL |
|---|---|
| Frontend | `http://localhost:5173` |
| Backend API | `http://localhost:8001` |
| API docs (Swagger) | `http://localhost:8001/docs` |
| Local mailbox (Mailpit) | `http://localhost:8025` — every email the API sends locally (notifications, the daily digest, staff invitations) lands here; nothing leaves the machine. `docker-compose.yml` points the API's `SMTP_*` at it. |
| PostgreSQL | `localhost:5432` |

The data refresh doesn't run on its own locally. Run it with `docker compose exec -T api python -m app.jobs.daily_refresh --force`; it uses API-Football quota.

## Rationale

Setup commands are exactly the kind of fact that goes stale fast if written in two places. Keeping them in one file (`STARTER.md` at the repository root, beside the `README.md` a new contributor opens first) and linking to it satisfies this documentation set's goal of avoiding duplicate information.

## Related documents

- [`../../STARTER.md`](../../STARTER.md) — exact setup commands, demo data and troubleshooting
- [`../../README.md`](../../README.md) — repository overview
- [`../architecture/system-overview.md`](../architecture/system-overview.md) — what these services are and how they relate
- [`coding-standards.md`](./coding-standards.md) — conventions to follow once your environment is running
