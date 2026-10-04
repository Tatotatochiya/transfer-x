---
title: "TransferX Product Specification"
last_updated: 2026-10-03
status: Active
owner: "TODO — assign a Product Owner"
---

# TransferX Product Specification

## Purpose

This is the master entry point for TransferX's documentation. It gives a short, accurate description of what the product currently is, then indexes every other document in the set. Read this first — everything else is one or two links away.

This document is intentionally an **outline with pointers**, not the content itself. Detailed information lives in the linked documents, each with a single responsibility, so that updating one fact only requires editing one place.

## Scope

In scope: what TransferX is today (grounded in the current codebase), and a map of where to find everything else.
Out of scope: implementation detail (see `architecture/` and `engineering/`), day-to-day backlog (see [Roadmap](./product/roadmap.md) and Linear), business strategy detail (see `business/`).

## Table of Contents

- [What TransferX is](#what-transferx-is)
- [Current state](#current-state)
- [Documentation map](#documentation-map)
  - [Business](#business)
  - [Product](#product)
  - [Architecture](#architecture)
  - [Engineering](#engineering)
  - [Operations](#operations)
  - [Security & Compliance](#security--compliance)
  - [Feature specs](#feature-specs)
  - [UI redesign](#ui-redesign-shipped)
  - [Tracking documents](#tracking-documents)
- [System diagram](#system-diagram)
- [Related documents](#related-documents)

## What TransferX is

TransferX is a web platform for football (soccer) player transfers. It connects **selling clubs**, **buying clubs**, **agents**, and **players** around a structured deal lifecycle: a club lists a player (auction, fixed price, or open to offers), other clubs bid or make offers, terms are negotiated, an agent (where the player has one) negotiates commission and personal terms, and the deal proceeds through a staged approval process to completion.

> **TODO:** Replace this paragraph with an approved product description once one exists in `business/vision.md`. This paragraph is derived directly from the current codebase (see `architecture/backend-architecture.md`) and should stay accurate to what's actually built, not aspirational.

## Current state

| Fact | Value | Source |
|---|---|---|
| Backend | FastAPI (Python), SQLAlchemy async, PostgreSQL | [`architecture/backend-architecture.md`](./architecture/backend-architecture.md) |
| Frontend | React 19, Vite, TypeScript, Tailwind CSS v4 | [`architecture/frontend-architecture.md`](./architecture/frontend-architecture.md) |
| Database migrations | 98 files, head at `0096` (Alembic) | [`engineering/database-migrations.md`](./engineering/database-migrations.md) |
| User types | Club (owner + 4 staff roles), Agent, Player, Admin | [`product/personas.md`](./product/personas.md) |
| Deal stages | AGREEMENT → AGENT_NEGOTIATION → PERSONAL_TERMS → PAPERWORK → CONFIRMED → COMPLETED (or COLLAPSED) | [`product/workflows/transfer-lifecycle.md`](./product/workflows/transfer-lifecycle.md) |
| Deal types | PERMANENT, LOAN (both offerable); FREE_TRANSFER, PRE_CONTRACT (derived by the signing paths) | [`product/workflows/transfer-lifecycle.md`](./product/workflows/transfer-lifecycle.md) |
| Deployed environment | Railway: live with demo data for the Premier League clubs; deployed from `main` by hand. Not a formally promoted staging or production environment. Check its migration head before relying on a feature from `0088` onwards (phone notifications, admin audit, Lite undo). | [`operations/environments-and-deployment.md`](./operations/environments-and-deployment.md) |
| Interfaces | The full app, and **Lite mode** for club directors (big-type home, Buy flow, action cards with a 10-second undo, Ask anything). Lite is opt-in per person. | [`feature_spec/lite-mode/`](./feature_spec/lite-mode/README.md) |
| Notifications | In-app (bell and live refresh), email (per type, plus the daily digest), and **phone push** (Web Push: tiers, quiet hours, a morning summary, a decision sheet, and the 30-minute email fallback) | [`feature_spec/mobile-notifications/`](./feature_spec/mobile-notifications/README.md) |
| AI assistant | Advises and never acts (ADR 0006): offer advisor, negotiation summary, terms checks, pricing, briefing, Ask anything, drafts | [`architecture/decisions/0006-ai-assistant-advises-from-scoped-facts.md`](./architecture/decisions/0006-ai-assistant-advises-from-scoped-facts.md) |
| Admin and accountability | Admin panel for TransferX staff; every admin change audited with a reason; Audit log page with Excel export; read-only "view as this club" | [`architecture/authentication-and-permissions.md`](./architecture/authentication-and-permissions.md) |
| Current plan | Phase 0 (ship what's in flight) to Phase 5, from the 3 October 2026 review | [`feature_spec/phased-plan-2026-q4/`](./feature_spec/phased-plan-2026-q4/README.md) |

> **TODO:** Keep this table in sync as the product evolves. It should always reflect *current, verified* state — if you're not sure a row is still accurate, check the code before trusting it.

## Documentation map

### Business
*Why the business exists, who it serves commercially, how it makes money.*

- [`business/README.md`](./business/README.md) — area overview
- [`business/vision.md`](./business/vision.md) — mission, problem statement
- [`business/target-users-and-market.md`](./business/target-users-and-market.md) — market and segment
- [`business/business-model.md`](./business/business-model.md) — pricing and monetization
- [`business/glossary.md`](./business/glossary.md) — canonical definitions of domain terms

### Product
*What to build, for which users, in what order — not how it's implemented.*

- [`product/README.md`](./product/README.md) — area overview
- [`product/roadmap.md`](./product/roadmap.md) — phased plan and links to the live backlog
- [`product/personas.md`](./product/personas.md) — who uses TransferX and in what role
- [`product/workflows/`](./product/workflows/README.md) — user-journey-level descriptions of core flows
  - [Transfer lifecycle](./product/workflows/transfer-lifecycle.md)
  - [Negotiation & offers](./product/workflows/negotiation-and-offers.md)
  - [Agent representation](./product/workflows/agent-representation.md)
  - [Deal completion](./product/workflows/deal-completion.md)
- [`product/decisions/`](./product/decisions/README.md) — record of significant product decisions

### Architecture
*How the system is designed.*

- [`architecture/README.md`](./architecture/README.md) — area overview
- [`architecture/system-overview.md`](./architecture/system-overview.md) — high-level system diagram and stack
- [`architecture/backend-architecture.md`](./architecture/backend-architecture.md) — FastAPI module layout
- [`architecture/frontend-architecture.md`](./architecture/frontend-architecture.md) — React app structure
- [`architecture/data-model.md`](./architecture/data-model.md) — core entities and relationships
- [`architecture/authentication-and-permissions.md`](./architecture/authentication-and-permissions.md) — how auth/authorization is implemented
- [`architecture/decisions/`](./architecture/decisions/README.md) — architecture decision records (ADRs)

### Engineering
*How to build, test, and work in this codebase day to day.*

- [`engineering/README.md`](./engineering/README.md) — area overview
- [`engineering/getting-started.md`](./engineering/getting-started.md) — local environment setup
- [`engineering/coding-standards.md`](./engineering/coding-standards.md) — conventions and style
- [`engineering/testing-strategy.md`](./engineering/testing-strategy.md) — how testing works and what's covered
- [`engineering/database-migrations.md`](./engineering/database-migrations.md) — Alembic workflow
- [`engineering/api-reference.md`](./engineering/api-reference.md) — where the API reference lives

### Operations
*How TransferX runs in production.*

- [`operations/README.md`](./operations/README.md) — area overview
- [`operations/environments-and-deployment.md`](./operations/environments-and-deployment.md) — environments and how deploys work
- [`operations/monitoring-and-observability.md`](./operations/monitoring-and-observability.md) — logging, metrics, alerting
- [`operations/incident-response.md`](./operations/incident-response.md) — what to do when something breaks

### Security & Compliance
*What's protected, what isn't, and what the legal exposure is.*

- [`security-and-compliance/README.md`](./security-and-compliance/README.md) — area overview
- [`security-and-compliance/permissions-model.md`](./security-and-compliance/permissions-model.md) — confidentiality and access posture
- [`security-and-compliance/data-privacy-and-legal.md`](./security-and-compliance/data-privacy-and-legal.md) — privacy and legal surface

### Feature specs
*Implementation-ready build specifications for upcoming features — point-in-time documents, superseded by the product/architecture docs once shipped.*

- [`feature_spec/README.md`](./feature_spec/README.md) — area overview and spec lifecycle
- [`feature_spec/fair-value-vs-asking-signal.md`](./feature_spec/fair-value-vs-asking-signal.md) — fair-value-vs-asking valuation signal (TRA-91/TRA-92) — **implemented 2026-07-07**
- [`feature_spec/injury-availability-risk-profile.md`](./feature_spec/injury-availability-risk-profile.md) — injury-availability risk profile (no ticket yet)
- [`feature_spec/club-team-roles-and-onboarding.md`](./feature_spec/club-team-roles-and-onboarding.md) — club team accounts, roles & onboarding (TRA-151/146/152/86 + two proposed) — **implemented 2026-07-10**
- [`feature_spec/loan-transfers.md`](./feature_spec/loan-transfers.md) — loans with options and obligations
- [`feature_spec/lite-mode/`](./feature_spec/lite-mode/README.md) — Lite mode for directors (L1–L6 built; L7 team contact and L8 decisions from email to come)
- [`feature_spec/player-profile-ledger/`](./feature_spec/player-profile-ledger/README.md) — the player profile's season ledger, career and injuries
- [`feature_spec/mobile-notifications/`](./feature_spec/mobile-notifications/README.md) — phone notifications, phases 1–4 built
- [`feature_spec/my-club-compact-squad/`](./feature_spec/my-club-compact-squad/README.md) — My Club's compact squad table
- [`feature_spec/compact-sidebar/`](./feature_spec/compact-sidebar/README.md) — the compact sidebar
- [`feature_spec/phased-plan-2026-q4/`](./feature_spec/phased-plan-2026-q4/README.md) — **the current plan**: Phase 0 to Phase 5 and the decisions needed

### UI redesign (shipped)
*Full frontend visual redesign — light theme with dark mode as a togglable preference (Account Settings), a four-tier information hierarchy, and a server-derived "whose move" state on every negotiation row. **Merged to `main` and deployed 2026-08-13**; the `redesign/ui-light-theme` branch is a full ancestor of `main`.*

- [`design_handoff_transferx/README.md`](./design_handoff_transferx/README.md) — overview, the four-tier hierarchy, the "whose move" rule, and what's in the package
- [`design_handoff_transferx/CLAUDE.md`](./design_handoff_transferx/CLAUDE.md) — non-negotiables for any session working on this
- [`design_handoff_transferx/BASELINE.md`](./design_handoff_transferx/BASELINE.md) — test baseline recorded before this work started; every phase's "done" is measured against this, not against "fully green"
- [`design_handoff_transferx/SESSIONS.md`](./design_handoff_transferx/SESSIONS.md) — the 13 frontend phases plus the parallel backend track (B1–B7); see [`IMPLEMENTATION_STATUS.md`](./IMPLEMENTATION_STATUS.md) for current, verified status of both — frontend Phases 0–12 and backend B1–B6 are shipped on `main`; B7 (present-value effect) remains deferred per `DECISIONS.md` item 5

### Tracking documents
*Root-level documents that track ongoing state rather than belonging to one area — see [`README.md#tracking-documents`](./README.md#tracking-documents) for the full explanation.*

- [`CHANGELOG.md`](./CHANGELOG.md) — chronological record of what changed
- [`IMPLEMENTATION_STATUS.md`](./IMPLEMENTATION_STATUS.md) — current build status, verified against code
- [`SESSION_HANDOVER.md`](./SESSION_HANDOVER.md) — the current handover note for the next working session

## System diagram

```mermaid
flowchart LR
    TODO[Diagram not yet created]
```

> **TODO:** Add a top-level system diagram (clients → API → database → external integrations) once reviewed. See [`architecture/system-overview.md`](./architecture/system-overview.md) for the detailed version this should summarize.

## Related documents

- [`docs/README.md`](./README.md) — documentation conventions and structure (read this if you're adding new docs)
- [`../.claude/skills/`](../.claude/skills/) — the five Claude Code project skills that encode this documentation system's conventions, plus engineering, product, and backlog standards, as procedural guidance
