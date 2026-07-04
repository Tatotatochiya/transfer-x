---
title: "Changelog"
last_updated: 2026-07-05
status: Active
owner: "TODO — assign a Documentation Owner"
---

# Changelog

## Purpose

A chronological record of what changed in TransferX — the "what happened, in order" complement to [`IMPLEMENTATION_STATUS.md`](./IMPLEMENTATION_STATUS.md), which answers "what's true right now." See that document's Purpose section for the exact split; don't let the two collapse into duplicates.

## Scope

In scope: user-visible and behaviour-affecting changes (features, fixes, removals), one entry per change.
Out of scope: internal refactors with no behaviour change, minor documentation wording fixes — not everything that happens needs an entry here.

## Format

Follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/): most recent changes at the top, grouped under `### Added` / `### Changed` / `### Fixed` / `### Removed`, with unreleased work under `## [Unreleased]`.

Maintained by the [`documentation-standards`](../.claude/skills/documentation-standards/SKILL.md) skill — update it as part of any session that ships a real change, not in a batch after the fact.

## [Unreleased]

### Fixed
- Deal room was unreachable for an invited agent until after their first negotiation write — `is_deal_participant`'s AGENT branch required an existing `AgentNegotiation` row; now also accepts a live (non-declined) `AgentDealInvitation`. (`backend/app/deals/room_service.py`)
- The mandated agent couldn't advance a deal from `AGENT_NEGOTIATION` to `PERSONAL_TERMS` — `advance_deal` only ever checked for a club profile. Restructured so a staff bypass is checked first, then the mandated-agent case, then the club case. (`backend/app/deals/router.py`, `backend/app/deals/service.py`)
- `PUT /deals/{id}/personal-terms` accepted terms from any agent on the deal, not just the one with the mandate — now checks the caller against `AgentNegotiation.agent_id`. (`backend/app/deals/router.py`)
- A pure staff/admin account (created via `create_superuser.py`, which has no linked club) got a 403 advancing `PAPERWORK → CONFIRMED`, because the club-profile check ran before the staff bypass. Staff bypass is now checked first, unconditionally. (`backend/app/deals/router.py`)
- Agent invitations kept appearing on the agent dashboard ("2 new deal invitations") after the deal had already collapsed or completed. `list_invitations` now joins `Deal` and filters to `IN_PROGRESS`/`PENDING_COMPLETION`. (`backend/app/agents/service.py`)
- Agent commission wasn't recorded unless the agent manually entered an absolute amount alongside the percentage, silently leaving no `AgentCommission` row. `upsert_negotiation_terms` now derives the amount from `commission_pct × agreed_fee` whenever only a percentage is given. (`backend/app/deals/service.py`)
- `AuditEvent.actor_user_id` was populated by no write path and was effectively always null, so the audit log couldn't say who did what. Every deal-mutating service function now threads the caller's user id through; the JSON `GET /deals/{id}/audit-log` endpoint also gained the actor-label resolution the CSV export already had. (`backend/app/deals/service.py`, `backend/app/deals/router.py`, `backend/app/audit/router.py`)
- **TRA-137** — `GET /deals/{id}` required a club profile, so the mandated agent and the transferring player got "Deal not found" opening their own deal. Now resolves any legitimate participant (club/agent/player/staff) via `room_service.is_deal_participant`, and the response hides commission terms from the player (club/agent business, mirroring `AgentNegotiation`'s existing field-scoping). (`backend/app/deals/router.py`)
- **TRA-138** — a club could list any player for sale, or accept a transfer naming itself as seller, with no check that the player was actually registered to them. `POST /sales` and `accept_offer` now validate ownership via a new `players_service.get_owning_club_id` (active contract, falling back to whoever created the player record — the same rule `update_my_club_player` already used). (`backend/app/sales/router.py`, `backend/app/offers/service.py`, `backend/app/players/service.py`)
- **TRA-139** — `GET /sales` and `GET /sales/{id}` leaked `reserve_price`, `best_bid`, and `bid_count` to any unauthenticated or rival-club viewer, defeating the platform's own anonymised order-book design. Now null for everyone except the seller and staff; `minimum_next_bid` stays visible since a bidder needs it to place a valid bid. (`backend/app/sales/router.py`, `backend/app/sales/schemas.py`)
- **TRA-140** — `GET /deals/{id}/medical-check` and `GET /deals/{id}/personal-terms` only required login, so any authenticated user could read any deal's medical status and proposed wages. Now scoped to deal participants. (`backend/app/deals/router.py`)
- **TRA-141** — `GET /deals/{id}/audit-log` and its CSV export had no participant check at all, and the CSV leaked raw actor UUIDs. Now scoped to deal participants, with actor UUIDs resolved to display labels in the export. (`backend/app/audit/router.py`)
- **TRA-127** — any agent could claim an unstarted `AgentNegotiation` and insert themselves into a deal they weren't invited to. `upsert_negotiation_terms` now checks the deal's `AgentDealInvitation` before allowing the first write. (`backend/app/deals/service.py`)
- **TRA-60** — a deal with no mandated agent skipped the `PERSONAL_TERMS` stage entirely, letting a player be transferred without ever consenting to their terms. `advance_deal`'s `AGREEMENT` branch now routes to `PERSONAL_TERMS` for every deal, and the buying club (not just an agent) can propose personal terms when no agent is involved. (`backend/app/deals/service.py`, `backend/app/deals/router.py`)
- Backend test suite was entirely uncollectable — `audit_events.payload_json` used PostgreSQL's `JSONB` type directly, which the SQLite test database can't create. Now `JSON().with_variant(JSONB, "postgresql")`, so Postgres is unaffected and the test suite (243 tests) runs again. (`backend/app/audit/models.py`)

### Changed
- **Personal terms consolidated to a single capture point** (see [ADR 0002](./product/decisions/0002-single-capture-point-for-personal-terms.md)) — previously captured twice (informally during `AGENT_NEGOTIATION`, again at `PERSONAL_TERMS`) with no reconciliation between the two. Now captured exactly once, at `PERSONAL_TERMS`, for both mandated and non-mandated deals, under one consistent account-gated proxy rule (the real player consents if they have an account; the mandated agent proxies only if they don't). `AgentNegotiation` lost its `proposed_wage_weekly`/`proposed_signing_bonus`/`proposed_length_years`/`player_agreement` columns (migration `0047_agent_negotiation_commission_only`); the frontend's `AgentNegotiationWorkspace` lost its player-side panel and `PlayerTermsProposalView` in favour of the existing Personal Terms panel gaining agent-proxy consent buttons. (`backend/app/agents/models.py`, `backend/app/deals/service.py`, `backend/app/deals/router.py`, `frontend/src/pages/deals/DealDetailPage.tsx`)
- Money inputs on the deal detail page (agreed fee, wage, signing bonus, instalment amounts, etc.) now comma-format as you type, via a new `FormattedNumberInput` component. (`frontend/src/components/ui/FormattedNumberInput.tsx`, `frontend/src/pages/deals/DealDetailPage.tsx`)
- The Terms card on the deal detail page now shows each club's crest next to its name — `ClubSummary` gained `crest_url` (the underlying club field already existed), and `ClubLink` renders it when passed, opt-in and backward-compatible for every other caller. (`backend/app/deals/schemas.py`, `frontend/src/components/ui/ClubLink.tsx`, `frontend/src/pages/deals/DealDetailPage.tsx`)
- The sidebar footer now makes the logged-in identity unambiguous — current role (Club/Agent/Player), a staff overlay badge when applicable, and the specific club/agent/player name, each with a consistent role color. New `useIdentity` hook normalizes identity across account types. (`frontend/src/hooks/useIdentity.ts`, `frontend/src/components/layout/Sidebar.tsx`)
- The deal timeline now renders the real server-side audit log (`GET /deals/{id}/audit-log`) instead of reconstructing an approximate one from client-side state — every stage advance, negotiation update, clause, instalment, and medical-check change now has a timestamp and an attributed actor. (`frontend/src/pages/deals/DealDetailPage.tsx`)

### Removed
- `player_respond_to_negotiation` endpoint and service function — superseded by the single personal-terms capture point above; a non-mandated player never had a parallel negotiation-stage terms flow to respond to in the first place. (`backend/app/deals/router.py`, `backend/app/deals/service.py`)

### Added
- Medical Check panel on the deal detail page (TRA-61) — every deal participant sees the current status/notes; staff get an inline control to set or update it, with a note when a `FAILED` status is blocking `PAPERWORK → CONFIRMED`. The backend endpoint (`PUT /deals/{id}/medical-check`) was already fully functional; this closes the previously-documented gap that nothing in the product actually called it. (`frontend/src/pages/deals/DealDetailPage.tsx`, `frontend/src/types/{api,enums}.ts`)
- Migration `0047_agent_negotiation_commission_only`.
- Regression tests: `test_staff_without_club_profile_can_advance_paperwork`, `test_clause_addition_is_audited` (`backend/tests/test_deals.py`); `test_invitation_disappears_once_deal_collapses`, `test_commission_amount_auto_derives_from_percentage`, `test_negotiation_and_consent_actions_are_audited` (`backend/tests/test_agent_negotiation.py`); `test_actor_user_id_populated_by_real_write_path`, `test_json_audit_log_resolves_actor_labels` (`backend/tests/test_audit.py`); `FormattedNumberInput.test.tsx` and `ClubLink.test.tsx` (frontend — 14 tests total across both).
- [ADR 0002: single capture point for personal terms](./product/decisions/0002-single-capture-point-for-personal-terms.md).
- Full documentation structure under `/docs` — business, product, architecture, engineering, operations, and security-and-compliance areas, plus this changelog, `IMPLEMENTATION_STATUS.md`, and `SESSION_HANDOVER.md`.
- Five Claude Code project skills under `.claude/skills/` (`documentation-standards`, `engineering-standards`, `linear-workflow`, `product-principles`, `session-lifecycle`) encoding how this repository expects to be worked in.
- Linear backlog refinement: consistent label taxonomy, legacy/superseded tickets archived, two regressions reopened against the tickets whose acceptance criteria they violate, and a set of new tickets covering gaps identified in a workflow audit.
- Regression tests: `backend/tests/test_agent_negotiation.py` and `backend/tests/test_audit.py` (new), plus additions to `backend/tests/test_deals.py`, `test_sales.py`, and `test_offers.py` covering personal-terms consent without an agent and the TRA-137/138/139/140/141 fixes above.

> **TODO:** Once this project starts cutting releases, replace `[Unreleased]` batches with dated version headings (e.g. `## [1.2.0] - 2026-08-01`) as they ship.

## Related documents

- [`IMPLEMENTATION_STATUS.md`](./IMPLEMENTATION_STATUS.md) — current verified state, as distinct from this history of changes
- [`PRODUCT_SPEC.md`](./PRODUCT_SPEC.md) — master index
- [`SESSION_HANDOVER.md`](./SESSION_HANDOVER.md) — the current, single-session handover note (not a history — see that document)
