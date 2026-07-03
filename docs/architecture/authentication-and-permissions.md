---
title: "Authentication & Permissions"
last_updated: 2026-07-03
status: Active
owner: "TODO — assign a Technical Lead"
---

# Authentication & Permissions

## Purpose

Documents **how** authentication and authorization are technically implemented. For **what is and isn't protected** — the risk/confidentiality posture rather than the mechanism — see [`../security-and-compliance/permissions-model.md`](../security-and-compliance/permissions-model.md). That split is deliberate: this document is implementation-facing, that one is risk-facing, and each has a single owner concern.

## Scope

In scope: authentication mechanism (JWT), the role/type model, and how authorization is enforced in code.
Out of scope: which specific endpoints have permission gaps today (tracked in the live backlog and summarized in [`../security-and-compliance/permissions-model.md`](../security-and-compliance/permissions-model.md), not duplicated here).

## Table of Contents

- [Authentication](#authentication)
- [Account types](#account-types)
- [Club roles](#club-roles)
- [Authorization pattern](#authorization-pattern)
- [Related documents](#related-documents)

## Authentication

JWT-based: a short-lived access token plus a longer-lived refresh token. The access token is held in memory on the frontend (not persisted); the refresh token is persisted and used to silently re-issue an access token.

> **TODO:** Document token lifetimes and the refresh flow in more detail.

## Account types

Every `User` has a type: **Club**, **Agent**, **Player**, **Staff**, or **Admin** (superuser). See [`../product/personas.md`](../product/personas.md) for what each role means at a product level.

## Club roles

Within a club account, a staff member has a role (e.g. manager vs. read-only) distinct from the club's primary owner login.

> **TODO:** Document the current club-staff role model and its capability boundaries.

## Authorization pattern

> **TODO:** Document the dependency-injection pattern used to gate routes (e.g. role-gated dependencies), and the general approach to checking whether a caller is a legitimate party to a given resource (club, deal, offer, etc.).

## Related documents

- [`../product/personas.md`](../product/personas.md) — what these roles mean at a product level
- [`../security-and-compliance/permissions-model.md`](../security-and-compliance/permissions-model.md) — confidentiality posture and known gaps
- [`backend-architecture.md`](./backend-architecture.md) — the `auth` module this document describes
