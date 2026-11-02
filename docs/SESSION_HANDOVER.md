---
title: "Session Handover"
last_updated: 2026-11-04
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

## Session Summary — 2026-11-04

A long session, 2026-10-12 to 2026-11-04: PRs #40–#58 merged, and #59 (this branch) open. Detail in [`CHANGELOG.md`](./CHANGELOG.md).

**Where things are**
- **Code:** `main` is at #58. This branch, `demo-auctions-and-controls`, adds auction bidding by house clubs, the "make them answer now" controls and this handover.
- **Migrations:** head is `0107`.
  - `0101`–`0103`: real-world moves.
  - `0104`: demo runs and journal, house clubs, testers.
  - `0105`: `deals.is_test`.
  - `0106`–`0107`: demo speed and rivals.
- **Railway:**
  - Deploys `main` automatically. It stalled from 19 to 29 October; the product owner restarted it.
  - Last checked on 2026-11-02, at #54: clean start, no errors.
  - `DEMO_ENABLED` is **not** set on Railway, so demo mode is off there.
- **Local:** `.env` has `DEMO_ENABLED=true`. House clubs: Man City, Man Utd, Tottenham, Aston Villa. No demo is open. The Chelsea account isn't a tester yet.
- **Tooling:**
  - The Railway CLI (`~/.local/bin/railway`) login expires silently. When it does, a "production" read falls back to the local database: check the host isn't `db` before trusting one.
  - Commits are authored as `Tatotatochiya <aashishpradhan@outlook.com>`.

**Completed work**
- **Lite:**
  - The Buy page is a search plus the club's shortlist; the guided suggestions are removed (#40, #48).
  - Lite is the default for club members, with a visible "Switch to full app" (#42).
  - Email decisions need the recipient signed in, and the confirm page no longer leaks the club's valuation (#43, #46).
- **Valuations:**
  - Calibrated against production fees: within ±25% of the fee went from 12% of transfers to 31%, and the median bias from −64% to −9% (#44).
  - Each player's last transfer fee now shows beside the value (#55).
- **Deadline day:** `/deadline`, a banner in the last 72 hours, and pushes 24, 6 and 2 hours before the close (#45).
- **Real-world moves:**
  - Staff apply or dismiss moves (#41), and clubs are alerted (#46).
  - TransferX's own deals count: completion is held while a move is unresolved, and the "behind TransferX" case is staff only (#50).
  - Admin links to the page are easier to find (#52).
- **Admin:**
  - Staff tools for a stuck deal, each with a reason (#47).
  - Test transfers can be marked (#53).
- **Fix:** Ask TransferX was broken on Railway by `litellm` 1.106; it's pinned to 1.103.2 (#49).
- **Buy and Sell** buttons in the top bar, on My Club and on squad rows (#54).
- **Demo mode** ([spec](./feature_spec/demo-mode.md), [architecture ADR 0009](./architecture/decisions/0009-demo-runs-journal-changes-reset-plays-them-back.md)):
  - demo runs journal every change, and reset plays them back with a "changed since" safety check (#51);
  - demo and test deals stay out of valuations, comparables and Recent Transfers (#53);
  - house clubs sell, buy, bid as rivals (#56, #58) and bid in auctions;
  - testers can make a house club answer now (#59).

**Important decisions** (product owner)
- Lite's guided buy suggestions are removed; Lite decision 3 is superseded.
- Valuations aim to match real fees, with a bounded lift below the elite.
- Real-world moves ([product ADR 0009](./product/decisions/0009-real-world-moves-flagged-applied-by-staff.md)):
  - only staff apply them, never automatically;
  - a move holds a deal's completion rather than only warning;
  - "TransferX ahead of the data" is staff only, and can't be applied.
- Demo mode runs in the same database (option B, with the journal), not a separate demo copy:
  - house clubs are unused clubs only;
  - in a demo the other side must be a house club;
  - rivals are never named, and appear "sometimes" (about one offer in three) by default.
- No scraping of fee sites; a licensed provider (Sportmonks) is to be evaluated for live market values.

**Outstanding work**
- **To switch demo mode on, on Railway:**
  - set `DEMO_ENABLED=true` on **both** `backend` and `stats-worker` (the 22:00 valuation refresh needs it, to leave open demos out);
  - then choose house clubs and testers in Admin → Demo.
- **Mark production's four test transfers** in Admin → Deals: Saka, Havertz, Rice (all from Arsenal) and Acheampong (Chelsea → Liverpool).
- **Apply real-world moves** in Admin → Real-world moves, a club at a time. There were 199 on 21 October. Applying can't be reset.
- **Valuation:** anchor the value to the last fee. Left over from the calibration: fees under £5m are over-predicted, £25m+ under-predicted, and smaller leagues need work.
- **Lite loans** (to-do since 13 October).
- **Pin the other backend packages,** or add a lock file.
- **Notifications:**
  - measure how many people have them on;
  - ask at the right moment;
  - keep urgent ones on screen on computers;
  - WhatsApp, later.
- **Admin:**
  - a "Needs attention" queue;
  - roles and two-factor sign-in;
  - an agents and mandates page (TRA-144: who confirms a mandate for a player with no account);
  - an email and message log;
  - retire the reason-less `/deals/{id}/staff/*` endpoints.
- **Still open from 2026-10-11 (status not checked this session):** the Slack webhook, an SMTP provider, and the real-phone notification test.
- **Uninvestigated:** `POST /lite/ask-team` returned 422 a few times in Railway's logs on 19 October.

**Risks**
- **Demo mode on the shared database:**
  - emails and pushes can't be undone;
  - a write made before a transaction touches a demo row isn't journaled (the reset safety check covers it);
  - any new feature reading completed deals must use `demo.service.shared_deals`;
  - without `DEMO_ENABLED` on `stats-worker`, an open demo's deals feed the 22:00 valuations.
- **Unpinned dependencies:** one release has already broken a deploy.
- **Full backend suite not run since 2026-10-17** (899 passed and 1 failed then; the failure was fixed in #43). Every PR since ran its related suites only.
- **Shared password on Railway accounts,** still: fine for a demo, not for real clubs.

**Recommended next task**
- Run the full backend suite once. Then switch demo mode on, on Railway (both services), add testers and house clubs, and play one buy and one sale end to end. Mark the four test transfers.

**Checks, as of 2026-11-04:**
- Backend: demo, sales and offers 143 passed; earlier this week the related suites passed 180 and 271.
- vitest 296 passed.
- `tsc -b` 0 errors.

## Related documents

- [`PRODUCT_SPEC.md`](./PRODUCT_SPEC.md): read first
- [`IMPLEMENTATION_STATUS.md`](./IMPLEMENTATION_STATUS.md): verified state and gaps
- [`CHANGELOG.md`](./CHANGELOG.md): history
