---
title: "Authentication & Permissions"
last_updated: 2026-07-04
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

Two layers, applied together:

1. **Route-level gates**, via FastAPI dependency injection — `get_current_user` (any authenticated user), role-specific variants (`get_seller_user`, `get_buyer_user`), and per-resource helpers that resolve "is this caller a legitimate party to resource X" before the handler body runs (e.g. `room_service.is_deal_participant(db, deal, current_user)` for a deal — true for the buyer/seller club, the transferring player, staff, or an agent — resolved via *either* an existing `AgentNegotiation` row *or* a live `AgentDealInvitation`, so an invited agent isn't locked out of the deal room before their first negotiation write creates the negotiation record). A caller who fails this gets `403`, never a `404` that would misleadingly imply the resource doesn't exist.
2. **Response-level field-scoping**, for resources where different legitimate participants shouldn't see every field — e.g. `AgentNegotiation`'s club-side terms are hidden from the player and vice versa; `Deal`'s commission fields are hidden from the player. Built by passing the caller's role into the response-builder function (`_build_neg_response`, `_build_deal_response`, `_build_personal_terms_response`) rather than a separate serializer per role.

A resource with a real ownership concept (e.g. a `Player`) is validated the same way on writes that create or transfer that ownership — see `players_service.get_owning_club_id`.

Two further, narrower patterns layered on top of the above:

- **Staff bypass takes priority over role-specific checks, not just over the party check.** `advance_deal`'s router checks `current_user.is_superuser` first, before even looking at `user_type` — a superuser account has no club, agent, or player profile of its own (`scripts/create_superuser.py` creates a bare `User` row), so any check that assumes an underlying club/agent/player profile must be skipped for staff, not merely satisfied by one.
- **Account-gated proxy**: a mandated agent may act on the player's behalf (responding to commission terms' player-side counterpart, consenting to personal terms) *only* when the player has no `PlayerProfile` of their own (`players_service.player_has_account`). Once a player registers, the agent's proxy access to that one action closes and the player must act themselves. Applied consistently at every point an agent could otherwise speak for a player, rather than per-endpoint.

## Related documents

- [`../product/personas.md`](../product/personas.md) — what these roles mean at a product level
- [`../security-and-compliance/permissions-model.md`](../security-and-compliance/permissions-model.md) — confidentiality posture and known gaps
- [`backend-architecture.md`](./backend-architecture.md) — the `auth` module this document describes
