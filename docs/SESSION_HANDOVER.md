---
title: "Session Handover"
last_updated: 2026-08-13
status: Active
owner: "TODO — assign a Documentation Owner"
---

# Session Handover

## Purpose

The single, current handover note between one working session and the next — human or Claude. Read this at the start of every session, right after [`PRODUCT_SPEC.md`](./PRODUCT_SPEC.md).

## Scope

In scope: the most recent session's summary — what's in motion right now.
Out of scope: full project history (see [`CHANGELOG.md`](./CHANGELOG.md)); this file is not a log.

## How this file works

This file is **overwritten**, not appended to, at the end of each session — maintained by the [`session-lifecycle`](../.claude/skills/session-lifecycle/SKILL.md) skill. It should always contain exactly one thing: the latest session's summary. If you want history, `CHANGELOG.md` has it; this file only needs to answer "what does the next session need to know right now."

## Latest Session Summary

**Session date:** 2026-08-13

**Completed work:**
- **Merged and shipped the entire UI redesign branch to `main`** (PRs #1 and #2), then continued working directly on `main`. `redesign/ui-light-theme` is a full ancestor — no divergence. Railway is deployed and at migration `0064`.
- **Backend track B1–B6** landed (`whose_move`, `GET /clubs/me/dashboard`, `/commitments`, `/contract-cliff`, market value-sort, wage fit) — the parallel work `design_handoff_transferx/SESSIONS.md` specified, which the frontend had been shipping against as documented client-side fallbacks. B7 stays deferred per `DECISIONS.md` item 5.
- **ADR 0003 — three-state `PlayerStatus`.** 7,825 contracted professionals stored as `FREE_AGENT` (green "available" badge) and were signable for £0 via `create_free_agent_deal`, which gated on that status alone. Added `EXTERNAL`, migration `0063`, defence-in-depth on the signing path. Audit finding C5.
- **ADR 0004 — anonymous buying club.** A buyer can approach undisclosed; the seller sees `A {league} club` and is told the offer *is* anonymous; the buyer is revealed on acceptance only. Migration `0064`. Masking is server-side and centralised.
- **Terminal-state honesty pass.** A resolved listing now says what resolved it; an accepted offer whose deal later collapsed no longer renders green "Accepted" (2 of 9 accepted offers were in that state). Both sides of the trade.
- **Offer Inbox** groups competing offers one row per player and splits In play / Closed. **Sidebar** gained "waiting on you" count badges (first consumer of B2). **War Room** Tier 1 is now server-derived from the same aggregate, sharing one query key.
- **Bugs fixed:** a 500 on any fee-less offer (`TypeError` formatting `None` in the D7 approval summary, failing for *every* caller); the offer form treating a blank fee and a deliberate free transfer as identical; a fifth site showing external-club players as "Free agent".
- **Docs:** ADRs 0003 and 0004, audit findings C5/H8/H9, `CHANGELOG.md`, `IMPLEMENTATION_STATUS.md`, `environments-and-deployment.md`, `design_handoff_transferx/DECISIONS.md` item 3.

**Important decisions:**
- **Anonymity is masked server-side in one function, never in the UI** ([ADR 0004](./architecture/decisions/0004-anonymous-buyer-masked-server-side.md)). Identity leaks through five fields, four of them ids resolvable via `GET /clubs/{id}` — a UI-only implementation would have been decorative. Acceptance is the only reveal; rejection/expiry leave the buyer permanently undisclosed, deliberately.
- **`PlayerStatus` gained a third state rather than a fifth display-layer override** ([ADR 0003](./architecture/decisions/0003-player-status-distinguishes-external-clubs.md)). Four such overrides already existed, each patching a read path while the write path stayed open.
- **Offer status is never rewritten to reflect its deal.** `ACCEPTED` stays truthful about the offer; the deal outcome is surfaced alongside it. Rewriting it would corrupt the audit trail and the re-list logic.
- **Sidebar badges are counts, not coloured dots** — `design_handoff_transferx/CLAUDE.md` rule 10 (colour is never the only carrier of meaning), and one red meaning "waiting on you" rather than a traffic-light scheme to learn.
- **The Railway listing repair was recorded as a no-op**, not a fix. Verified by direct read-only query: Railway never had the broken rows. The prior assumption that it did was untested and wrong — corrected in `CHANGELOG.md` and `operations/environments-and-deployment.md`.

**Outstanding work:**
- **47 pre-existing TypeScript errors** (audit [H9](./DEMO_READINESS_AUDIT.md)). ~25 are genuine type mismatches in app code (e.g. `AdminPlayerDetailPage` reads `Player.contracts`, which does not exist), ~14 unused declarations, ~6 test-fixture drift. Untriaged.
- **Audit [H8](./DEMO_READINESS_AUDIT.md)** — `PublicRoute` does not wait for token bootstrap, so refreshing or deep-linking any of ten market routes silently downgrades you to the anonymous view, losing `fair_value_signal`, `bid_count`, and a seller's own reserve price. Contained fix in `App.tsx`.
- **Anonymity does not cover auction bids** — separate model, separate order book. A buyer can be anonymous on an offer and named on a bid for the same player.
- **Offering for an `EXTERNAL` player creates an offer with `to_club_id = null`** that no club can ever accept. It reserves budget and expires in 14 days. Product decision, not a display bug.
- **Everything from the previous handover that this session did not touch:** C3 (close self-registration — still the oldest open decision, still unenforced), H1 (`isError` on list pages), H2 (3 dead `AdminHealthPage` links), H3 (row locks). Demo generator market scenarios M1–M4, S1–S2. The orphaned £15,000,001 committed budget on Liverpool's W. Fofana deal. `deal_sla`/`expire_mandates` job bodies still unverified.
- **The 16 frontend test failures are stale fixtures** (audit M11), a subset of the original 23. `testing-strategy.md` remains stale (claims 19 backend files/274 tests; actual is higher).

**Risks:**
- **Every "tsc clean" claim before 2026-08-13 is void as evidence.** `npx tsc --noEmit` resolves a project-references stub with `"files": []` and checks nothing, always exiting 0. Production builds were never affected (`package.json` runs `tsc -b`), but the verification command was not the check it was believed to be. **Use `npx tsc -b --noEmit`.**
- **Work is now committed directly to `main`**, not to a branch. Nine commits this session went straight to `origin/main` with no PR review step.
- **A seller can accept an anonymous offer without knowing the counterparty.** Bounded by their ability to reject, and they are told the offer is anonymous — but acceptance is binding, and this was a deliberate product choice worth revisiting if it surprises anyone.
- **Deleting an offer row with raw SQL strands its budget reservation.** Release only happens through the service layer; a direct `DELETE` left £1m orphaned in Liverpool's `transfer_reserved` mid-session (caught and reconciled). Withdraw through the API instead.
- Carried forward, all still true: **`commission_pct` is a fraction, not a percentage**; **`commissionpayer` is `BUYER`/`SELLER`/`PLAYER`**; **`app.clubs.service` must be imported explicitly in standalone scripts**; **the frontend Docker service is a production build** — rebuild before any browser check; **every dev password is `password123`**, including on Railway.

**Recommended next task:**
- **Triage the 47 TypeScript errors**, starting with the ~25 real mismatches. They are the only item where the codebase and its own types actively disagree, and they were invisible for the whole project until now — `AdminPlayerDetailPage` reading a non-existent `Player.contracts` is a runtime bug waiting for someone to open that page. Add `tsc -b --noEmit` to CI so the check cannot silently no-op again.
- If preferring a product-facing task instead: **C3 — close self-registration** remains the highest-value item outside that, and is now the longest-standing open decision in the project.

## Related documents

- [`PRODUCT_SPEC.md`](./PRODUCT_SPEC.md) — read this first, then this file
- [`CHANGELOG.md`](./CHANGELOG.md) — full change history
- [`IMPLEMENTATION_STATUS.md`](./IMPLEMENTATION_STATUS.md) — current verified build status
