---
title: "Permissions Model — Risk Posture"
last_updated: 2026-07-04
status: Active
owner: "TODO — assign a Security Owner"
---

# Permissions Model — Risk Posture

## Purpose

Describes what is and isn't protected in TransferX today from a confidentiality/access standpoint — the risk-facing view. For how authentication and authorization are technically implemented, see [`../architecture/authentication-and-permissions.md`](../architecture/authentication-and-permissions.md); this document doesn't repeat that mechanism, only assesses it.

## Scope

In scope: confidentiality boundaries between parties (e.g. clubs, agents, players), and known gaps.
Out of scope: implementation mechanism (see [`../architecture/authentication-and-permissions.md`](../architecture/authentication-and-permissions.md)).

## Table of Contents

- [Confidentiality boundaries](#confidentiality-boundaries)
- [Known gaps](#known-gaps)
- [Related documents](#related-documents)

## Confidentiality boundaries

**Verified 2026-07-04** against the code (see [`CHANGELOG.md`](../CHANGELOG.md) for the fixes that closed the gaps this table used to list as open).

| Entity / field | Who can see it | Enforced in |
|---|---|---|
| Sale `reserve_price`, `best_bid`, `bid_count` | Seller club, staff. `minimum_next_bid` stays visible to everyone — a bidder needs it to place a valid bid at all. | `GET /sales`, `GET /sales/{id}` |
| Deal medical check | Buyer club, seller club, mandated agent, the player, staff | `GET /deals/{id}/medical-check` |
| Deal personal terms | Same participants as above | `GET /deals/{id}/personal-terms` |
| Deal detail (stage, terms, notes, clauses, etc.) | Same participants as above | `GET /deals/{id}` |
| Deal commission terms (`agent_commission_pct`/`amount`, `commission_payer`, `commission_agent_id`) | Buyer club, seller club, mandated agent, staff — **not** the player, mirroring the same split already used for `AgentNegotiation` | `GET /deals/{id}` (field-scoped response) |
| Deal audit log (+ CSV export) | Same participants as the deal itself | `GET /deals/{id}/audit-log`, `GET /deals/{id}/audit-log/export.csv` |
| Player registration/ownership | A club can only list a player for sale, or accept a transfer naming them as seller, if that player is actually registered to them (active contract, or — before a contract exists — whichever club created the player record) | `POST /sales`, `POST /offers/{id}/accept` |

## Known gaps

- **`AuditEvent.actor_user_id` is effectively always null.** No current write path populates it (found while fixing the audit-log scoping above) — the audit log reliably records *what* happened and *when*, but not reliably *who* did it. Not a confidentiality leak by itself, but it undermines the log's value as an accountability record for a "paying club/agent will actually audit" feature. Not yet ticketed.
- **Player identity claims aren't attested** — a player self-registers a claim to a `Player` record with no verification step (Linear TRA-143).
- **Agent mandates don't require player confirmation** — a mandate can take effect without the player confirming it (Linear TRA-144).
- **Deal access is per club-owner-account only**, not extended to other staff at the same club (Linear TRA-146).

## Related documents

- [`../architecture/authentication-and-permissions.md`](../architecture/authentication-and-permissions.md) — the technical mechanism
- [`data-privacy-and-legal.md`](./data-privacy-and-legal.md) — the legal dimension of data exposure
- [`../product/personas.md`](../product/personas.md) — the parties whose confidentiality this document protects
