---
title: "Operations Documentation — Overview"
last_updated: 2026-10-11
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

TransferX runs on Railway (one environment, with demo data). Admin → Jobs, Errors and Health are the operational screens. See [`environments-and-deployment.md`](./environments-and-deployment.md).

## Related Documents

- [`../PRODUCT_SPEC.md`](../PRODUCT_SPEC.md) — master index
- [`../architecture/system-overview.md`](../architecture/system-overview.md) — the system these operations run
- [`../security-and-compliance/README.md`](../security-and-compliance/README.md) — security posture relevant to operating this system
