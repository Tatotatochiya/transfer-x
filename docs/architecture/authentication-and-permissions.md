---
title: "Authentication & Permissions"
last_updated: 2026-07-10
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

A club is a team, not a login. The club's primary account is the **OWNER** (a `User`, not a `ClubStaff` row); staff members are separate `User` accounts (always `user_type = CLUB` — `UserType.STAFF` is a reserved, deliberately unassigned value) linked via a `ClubStaff` row carrying one of four roles. Capabilities are enumerated in a single static matrix in `app/clubs/capabilities.py` — the only source of truth; the frontend consumes it via `GET /clubs/me/membership` and never re-derives it.

| Capability | OWNER | SPORTING_DIRECTOR | MANAGER | SCOUT | READONLY |
|---|---|---|---|---|---|
| View club data (squad, finance, listings, offers, deals) | ✓ | ✓ | ✓ | ✓ | ✓ |
| `SCOUTING_WRITE` — shortlists, player interest | ✓ | ✓ | ✓ | ✓ | ✗ |
| `MARKET_WRITE` — sales, bids, offers (incl. negotiation messages), squad edits | ✓ | ✓ | ✓ † | ✗ | ✗ |
| `DEAL_WRITE` — deal lifecycle, terms, clauses, instalments, deal-room writes | ✓ | ✓ | ✓ † | ✗ | ✗ |
| `CLUB_ADMIN` — club profile edit, verification request | ✓ | ✓ | ✗ | ✗ | ✗ |
| `TEAM_MANAGE` — invite/remove staff, change roles, approval policy | ✓ | ✗ | ✗ | ✗ | ✗ |
| `APPROVE_ACTIONS` — decide pending spending approvals | ✓ | ✓ | ✗ | ✗ | ✗ |

† MANAGER money-committing market actions (place bid, create/accept offer, accept bid) at or above the club's optional `approval_threshold` are captured as pending approvals instead of executing — see the approvals flow below.

Viewing is not a capability — club data visibility comes with membership itself. Enforcement is `require_club_capability(cap)` (a FastAPI dependency) on club-only endpoints, or an inline `ensure_club_capability` call inside the club branch of mixed-caller endpoints (e.g. deal advance, personal terms). Shared surfaces like the deal room use `ensure_capability_if_club_member`, which no-ops for agents/players (they're authorized by the participant check instead). Check order everywhere: superuser bypass first, then owner → all capabilities, then staff → matrix, else 403.

**Staff onboarding** is invitation-based provisioning, never open signup: the owner invites by email + role; a single-use token (sha256-hashed at rest, 7-day expiry) is emailed and returned exactly once in the create response; the invitee sets their own password at `POST /auth/invitations/{token}/accept` and is logged straight in. Removal deletes the `ClubStaff` row **and** deactivates the `User` (`is_active=False`, checked on every request) — access dies immediately, live JWT or not.

**Spending approvals** (per-club, single-amount policy on `ClubFinance.approval_threshold`, null = off): a captured action stores its validated payload in `pending_approvals` — nothing reserved, nothing executed. OWNER/SPORTING_DIRECTOR approve (re-executing with everything re-validated fresh; domain failures land `APPROVED_FAILED` with reason) or reject; the requester may cancel; a daily job expires stale requests after 24h. The approval row records both requester and decider.

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
