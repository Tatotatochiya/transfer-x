---
title: "Operations Documentation — Overview"
last_updated: 2026-07-03
status: Active
owner: "TODO — assign an Operations Owner"
---

# Operations Documentation

## Purpose

This area answers **how TransferX runs in production** — environments, deployment, monitoring, and incident response.

## Scope

In scope: production environments, deployment process, observability, incident handling.
Out of scope: local development (see [`../engineering/README.md`](../engineering/README.md)), system design (see [`../architecture/README.md`](../architecture/README.md)).

## Table of Contents

| Document | Purpose |
|---|---|
| [`environments-and-deployment.md`](./environments-and-deployment.md) | Environments and how deploys work |
| [`monitoring-and-observability.md`](./monitoring-and-observability.md) | Logging, metrics, alerting |
| [`incident-response.md`](./incident-response.md) | What to do when something breaks |

> **Note:** As of this writing, TransferX has no production environment configured — this area is largely forward-looking. See [`environments-and-deployment.md`](./environments-and-deployment.md) for current status.

## Related Documents

- [`../PRODUCT_SPEC.md`](../PRODUCT_SPEC.md) — master index
- [`../architecture/system-overview.md`](../architecture/system-overview.md) — the system these operations run
- [`../security-and-compliance/README.md`](../security-and-compliance/README.md) — security posture relevant to operating this system
