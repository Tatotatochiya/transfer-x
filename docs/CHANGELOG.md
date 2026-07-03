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

### Added
- Full documentation structure under `/docs` — business, product, architecture, engineering, operations, and security-and-compliance areas, plus this changelog, `IMPLEMENTATION_STATUS.md`, and `SESSION_HANDOVER.md`.
- Five Claude Code project skills under `.claude/skills/` (`documentation-standards`, `engineering-standards`, `linear-workflow`, `product-principles`, `session-lifecycle`) encoding how this repository expects to be worked in.
- Linear backlog refinement: consistent label taxonomy, legacy/superseded tickets archived, two regressions reopened against the tickets whose acceptance criteria they violate, and a set of new tickets covering gaps identified in a workflow audit.

> **TODO:** Once this project starts cutting releases, replace `[Unreleased]` batches with dated version headings (e.g. `## [1.2.0] - 2026-08-01`) as they ship.

## Related documents

- [`IMPLEMENTATION_STATUS.md`](./IMPLEMENTATION_STATUS.md) — current verified state, as distinct from this history of changes
- [`PRODUCT_SPEC.md`](./PRODUCT_SPEC.md) — master index
- [`SESSION_HANDOVER.md`](./SESSION_HANDOVER.md) — the current, single-session handover note (not a history — see that document)
