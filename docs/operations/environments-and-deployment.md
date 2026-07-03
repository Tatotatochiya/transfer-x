---
title: "Environments & Deployment"
last_updated: 2026-07-03
status: Draft
owner: "TODO — assign an Operations Owner"
---

# Environments & Deployment

## Purpose

Documents what environments TransferX runs in and how code gets deployed to them.

## Scope

In scope: environment list, deployment process.
Out of scope: local dev setup (see [`../engineering/getting-started.md`](../engineering/getting-started.md)).

## Table of Contents

- [Environments](#environments)
- [Deployment process](#deployment-process)
- [Related documents](#related-documents)

## Environments

| Environment | Status |
|---|---|
| Local development | Configured — Docker Compose (`db`, `api`, `frontend`) |
| Staging | Not yet configured |
| Production | Not yet configured |

> **TODO:** This is an honest current-state snapshot, not a plan. Fill in staging/production once they exist, and turn the gap into a roadmap item in [`../product/roadmap.md`](../product/roadmap.md) if it isn't tracked there already.

## Deployment process

> **TODO:** Document the deployment process once one exists — CI/CD pipeline, promotion strategy, rollback procedure.

## Related documents

- [`../architecture/system-overview.md`](../architecture/system-overview.md) — the system being deployed
- [`../engineering/getting-started.md`](../engineering/getting-started.md) — the local-only equivalent that exists today
- [`monitoring-and-observability.md`](./monitoring-and-observability.md) — how a deployed system would be observed
