---
title: "Security & Compliance Documentation — Overview"
last_updated: 2026-07-03
status: Active
owner: "TODO — assign a Security/Compliance Owner"
---

# Security & Compliance Documentation

## Purpose

This area answers **what's protected, what isn't, and what the legal/compliance exposure is** — the risk posture of the system, as distinct from how it's technically implemented (see [`../architecture/authentication-and-permissions.md`](../architecture/authentication-and-permissions.md) for the mechanism).

## Scope

In scope: confidentiality/permissions posture, data privacy, and legal-adjacent technical surface (e.g. terms of service, consent tracking).
Out of scope: how authentication/authorization is implemented in code (see [`../architecture/authentication-and-permissions.md`](../architecture/authentication-and-permissions.md)), business/commercial legal structure (see [`../business/`](../business/README.md)).

## Table of Contents

| Document | Purpose |
|---|---|
| [`permissions-model.md`](./permissions-model.md) | Confidentiality and access posture — what's protected today, what's known to need work |
| [`data-privacy-and-legal.md`](./data-privacy-and-legal.md) | Data privacy and legal-adjacent surface |

## Related Documents

- [`../PRODUCT_SPEC.md`](../PRODUCT_SPEC.md) — master index
- [`../architecture/authentication-and-permissions.md`](../architecture/authentication-and-permissions.md) — the technical mechanism this area assesses
