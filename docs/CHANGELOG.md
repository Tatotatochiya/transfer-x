---
title: "Changelog"
last_updated: 2026-07-03
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
- **TRA-127** — any agent could claim an unstarted `AgentNegotiation` and insert themselves into a deal they weren't invited to. `upsert_negotiation_terms` now checks the deal's `AgentDealInvitation` before allowing the first write. (`backend/app/deals/service.py`)
- **TRA-60** — a deal with no mandated agent skipped the `PERSONAL_TERMS` stage entirely, letting a player be transferred without ever consenting to their terms. `advance_deal`'s `AGREEMENT` branch now routes to `PERSONAL_TERMS` for every deal, and the buying club (not just an agent) can propose personal terms when no agent is involved. (`backend/app/deals/service.py`, `backend/app/deals/router.py`)
- Backend test suite was entirely uncollectable — `audit_events.payload_json` used PostgreSQL's `JSONB` type directly, which the SQLite test database can't create. Now `JSON().with_variant(JSONB, "postgresql")`, so Postgres is unaffected and the test suite (243 tests) runs again. (`backend/app/audit/models.py`)

### Added
- Full documentation structure under `/docs` — business, product, architecture, engineering, operations, and security-and-compliance areas, plus this changelog, `IMPLEMENTATION_STATUS.md`, and `SESSION_HANDOVER.md`.
- Five Claude Code project skills under `.claude/skills/` (`documentation-standards`, `engineering-standards`, `linear-workflow`, `product-principles`, `session-lifecycle`) encoding how this repository expects to be worked in.
- Linear backlog refinement: consistent label taxonomy, legacy/superseded tickets archived, two regressions reopened against the tickets whose acceptance criteria they violate, and a set of new tickets covering gaps identified in a workflow audit.
- Regression tests: `backend/tests/test_agent_negotiation.py` (new), plus additions to `backend/tests/test_deals.py` covering personal-terms consent without an agent.

> **TODO:** Once this project starts cutting releases, replace `[Unreleased]` batches with dated version headings (e.g. `## [1.2.0] - 2026-08-01`) as they ship.

## Related documents

- [`IMPLEMENTATION_STATUS.md`](./IMPLEMENTATION_STATUS.md) — current verified state, as distinct from this history of changes
- [`PRODUCT_SPEC.md`](./PRODUCT_SPEC.md) — master index
- [`SESSION_HANDOVER.md`](./SESSION_HANDOVER.md) — the current, single-session handover note (not a history — see that document)
