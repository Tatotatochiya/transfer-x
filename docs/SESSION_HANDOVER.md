---
title: "Session Handover"
last_updated: 2026-11-11
status: Active
owner: "TODO — assign a Documentation Owner"
---

# Session Handover

## Purpose

The single, current handover note between one working session and the next, human or Claude. Read it at the start of every session, right after [`PRODUCT_SPEC.md`](./PRODUCT_SPEC.md).

## Scope

In scope: the latest session's summary, what's in motion now.
Out of scope: history ([`CHANGELOG.md`](./CHANGELOG.md)). This file is overwritten, not appended to.

## How this file works

Overwritten at the end of each session by the [`session-lifecycle`](../.claude/skills/session-lifecycle/SKILL.md) skill. It holds exactly one thing: the latest summary.

## Latest Session Summary

## Session Summary — 2026-11-11 (type and colour)

**Completed work:**
- Built [`type-and-colour`](./feature_spec/type-and-colour/README.md) on branch `type-and-colour` (15 commits, not yet pushed): type roles and colour tokens in `index.css`; shared components; colour meanings (AI violet, neutral categories, blue only for tappable, `primary-success` removed, `text-on-accent`); one compact money format; the sweep of every area including Lite and admin; blue dark-mode accent; a second pass so Caption is only for labels.
- `frontend/src/test/designSystem.test.ts`: banned classes with a ratchet allowlist (now empty) and contrast pairs in both themes. `npm run check:design`.
- Measured with `measure-type.mjs`'s `measure()` over CDP: 0% under 13px and ≤ 6 sizes on every measured route at 390 and 1280.
- Docs: TOKENS.md (typography, colour roles, money), RESPONSIVE.md, SCREENS.md note, CHANGELOG, feature_spec index, IMPLEMENTATION_STATUS.
- `STARTER.md` (new, repo root): fresh clone to running app with the reference snapshot, Premier League clubs and demo deals; `.env.example` rewritten to cover every setting. README, getting-started, docs home, PRODUCT_SPEC, RULES, coding standards, testing strategy, frontend architecture and database migrations brought up to date.
- Checked on a scratch database (`tx_starter_check`, dropped afterwards): restore, `alembic upgrade head`, onboarding, demo seed and account scripts. That found two bugs, both fixed: migration `0062` collided with the snapshot's `vendor_sync_runs`, and `seed_demo.py` was missing model imports.
- Tests: backend 938 passed, frontend 480 passed (65 files), `tsc -b` clean.

**Important decisions:**
- Q1 default taken: dark accent is blue with dark text on it. Q2: admin swept in the same PR.
- Caption (13px) is for labels, badges, counts and timestamps; sentences and meta lines are Small (14). Deviations are listed in the spec's §15.

**Outstanding work:**
- Push `type-and-colour` and open the PR (waiting for the user's go-ahead). It also carries `STARTER.md` and the two setup fixes.
- `STARTER.md` hasn't been followed on a truly fresh clone (a new machine or `docker compose down -v`); the steps were checked on a scratch database beside the existing one.
- The reference snapshot is from 2026-08-08: new demo accounts and data since then come only from the scripts. A fresh snapshot would shorten the starter.
- Not checked: the Deal room (no local deal with a signed-in party), 768px, 200% zoom, a real iPhone, Lite offer card.
- Most text is 14px rather than 15px on Dashboard, Player, Offer, Account and Make an offer.
- Production: one club's weekly wage budget of about £50M needs a staff correction (carried over).

**Risks:**
- Large visual change across every page: wraps or clipping in tight rows that the by-hand pass didn't reach. Positions lost their colours (fallback in the spec's §13).
- Dark-mode users see the accent change from green to blue.

**Recommended next task:**
- Review and merge the type-and-colour PR, check the Deal room and Lite offer card by hand, then the registration checklist.

## Related documents

- [`PRODUCT_SPEC.md`](./PRODUCT_SPEC.md): read first
- [`IMPLEMENTATION_STATUS.md`](./IMPLEMENTATION_STATUS.md): verified state and gaps
- [`CHANGELOG.md`](./CHANGELOG.md): history
