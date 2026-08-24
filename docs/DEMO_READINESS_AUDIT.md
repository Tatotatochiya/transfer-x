---
title: "Demo Readiness Audit — Investors & Prospective Clients"
last_updated: 2026-08-13
status: Active
owner: "TODO — assign a Product Owner"
---

# Demo Readiness Audit — Investors & Prospective Clients

## Purpose

A point-in-time assessment of whether TransferX can be demonstrated credibly to (a) early investors and (b) prospective client clubs, and what would undermine that demo.

This is a **merged audit**, consolidating two independent reviews of the same codebase on 2026-08-08. The reviews had markedly different blind spots — one swept backend correctness, data freshness, and security severity; the other swept frontend failure modes and demo-day mechanics. Every finding retained below was **independently verified against the running system**. Claims from either review that did not survive verification are recorded in [Corrections](#corrections--claims-that-did-not-survive-verification) rather than silently dropped, so nobody re-derives them later.

This is a *point-in-time document*, like a [`feature_spec/`](./feature_spec/README.md) — not living state. Once its findings are addressed, the durable facts belong in [`IMPLEMENTATION_STATUS.md`](./IMPLEMENTATION_STATUS.md) and [`security-and-compliance/permissions-model.md`](./security-and-compliance/permissions-model.md), and this file becomes history.

## Scope

In scope: demo-blocking defects, missing features a professional counterparty will expect, and data-state problems that make the product look worse than it is.
Out of scope: production hardening beyond what a demo or early pilot needs (see [`operations/`](./operations/README.md)), commercial strategy (see [`business/`](./business/README.md)), code style.

## Table of Contents

- [How to read this](#how-to-read-this)
- [Verification method](#verification-method)
- [Findings summary](#findings-summary)
- [Critical findings](#critical-findings)
- [High findings](#high-findings)
- [Medium findings](#medium-findings)
- [Low findings](#low-findings)
- [Corrections — claims that did not survive verification](#corrections--claims-that-did-not-survive-verification)
- [What is genuinely demo-ready](#what-is-genuinely-demo-ready)
- [Recommended pre-demo sequence](#recommended-pre-demo-sequence)
- [Related documents](#related-documents)

## How to read this

The two audiences fail differently, and conflating them produces a bad priority order:

| Audience | What kills the demo |
|---|---|
| **Investor** | The story doesn't render. Empty screens, a differentiator showing stale or absent numbers, a flow that dead-ends mid-narrative. They are watching whether the product *exists* and whether the wedge is real. |
| **Prospective client club** | The product isn't *trustworthy*. A Sporting Director asks "who verified that's really the player?" or "can my scout accidentally accept a £40m bid?" and the answer is bad. They are watching whether this survives contact with their legal, finance, and compliance functions. |

Each finding is tagged **Blocks demo** (the scripted walkthrough visibly breaks or looks empty) and/or **Blocks pilot** (the demo runs fine, but the answer to an obvious question loses the room or fails procurement).

Severity reflects impact on those two outcomes, not code-quality aesthetics.

## Verification method

Every finding below was checked directly against the running stack. Where a finding says "verified live", it means an actual request, not a code reading.

- Backend test suite: `pytest tests/` → **403 passed, 0 failed** (5m36s).
- Frontend test suite: `vitest run` → **96 passed, 23 failed** (9 files); every failure traced to root cause.
- TypeScript: `tsc --noEmit` → clean, exit 0. ~~Recorded as evidence at the time.~~ **Void — see [H9](#h9-the-frontend-type-check-has-been-passing-without-checking-anything).** That command resolves a project-references stub with `"files": []` and checks nothing. The correct invocation, `tsc -b --noEmit`, reports 44 errors and did so on this same commit.
- Migrations: `alembic current` → **0059, at head**. No pending migrations.
- API logs: no errors, exceptions, or 500s in 60 minutes of runtime.
- Database queried directly for deals, sales, offers, valuations, transfer windows, finance schema.
- Live exploit test against `POST /auth/register` (test account created and **deleted afterwards**).
- Route tables, row-lock usage, scheduler registration, and error-state handling read directly from source.

## Findings summary

| ID | Finding | Severity | Blocks demo | Blocks pilot |
|---|---|---|---|---|
| C1 | No deal in a demonstrable in-progress stage — the core lifecycle has no live example | **Critical** | ✅ | — |
| C2 | The entire demo dataset exists only in a local Docker volume, with no snapshot or seed script | **Critical** | ✅ | — |
| C3 | Anyone can claim any player's identity via open registration | **Critical** | — | ✅ |
| C4 | Daily background jobs never run if the API restarts within 24h; valuations are a month stale | **Critical** | ✅ | ✅ |
| C5 | 7,825 contracted professionals displayed as free agents — and were signable for £0 | **Critical** | ✅ | ✅ |
| H1 | List pages render a convincing "no data" empty state when the backend is down | **High** | ✅ | ✅ |
| H2 | Admin Health page has three dead links (guaranteed 404) | **High** | ✅ | — |
| H3 | No row locks on offer accept, deal completion, or instalment payment | **High** | — | ✅ |
| H4 | Agent mandates activate with no player confirmation | **High** | — | ✅ |
| H5 | Verification status gates nothing — it is a decorative badge | **High** | — | ✅ |
| H6 | No password reset flow of any kind | **High** | — | ✅ |
| H7 | Deal stages can deadlock, requiring superuser intervention to unstick | **High** | ✅ | ✅ |
| H8 | Refreshing or deep-linking any market page silently downgrades you to the anonymous view | **High** | ✅ | ✅ |
| H9 | The frontend type check has been passing without checking anything; 44 real errors were hidden | **High** | — | ✅ |
| M1 | Two Accept-bid affordances on one page; one has no confirmation and no capability check | **Medium** | ✅ | ✅ |
| M2 | "Rumors coming soon" placeholder on the public transfers page | **Medium** | ✅ | — |
| M3 | `console.error` on every failed login; `console.log` at module scope in production | **Medium** | ✅ | — |
| M4 | WebSocket reconnection has no UI feedback | **Medium** | ✅ | — |
| M5 | Analytics flush URL is broken in the built bundle | **Medium** | — | — |
| M6 | Bare `except Exception: pass` swallows vendor API failures | **Medium** | — | ✅ |
| M7 | Email sending disabled by default — invitations and notifications don't arrive | **Medium** | ✅ | ✅ |
| M8 | Money fields accept negative values | **Medium** | — | ✅ |
| M9 | Player profile save gives no error feedback on failure | **Medium** | — | — |
| M10 | No rate limiting on registration | **Medium** | — | ✅ |
| M11 | 23 failing frontend tests — all stale, but the suite is not a safety net | **Medium** | — | — |

---

## Critical findings

### C1. The core product story has no live example to demonstrate

**Blocks demo.**

TransferX's central claim is a structured, staged deal lifecycle. The database contains four deals:

| Stage | Status | Count |
|---|---|---|
| `COMPLETED` | `COMPLETED` | 3 |
| `PERSONAL_TERMS` | `COLLAPSED` | 1 |

**Not one deal sits in an active, in-progress stage.** Every stage between agreement and completion — `AGREEMENT`, `AGENT_NEGOTIATION`, `PERSONAL_TERMS`, `PAPERWORK`, `CONFIRMED` — has zero demonstrable instances. The deal room, agent commission negotiation, personal-terms consent, the medical-check panel, the audit timeline, and stage advancement **cannot be shown on live data**. These are the most differentiated parts of the product and the substance of [`product/workflows/transfer-lifecycle.md`](./product/workflows/transfer-lifecycle.md).

Supporting market data is equally thin:

- **Sales:** 3 total — 1 open auction, 1 open-to-offers, 1 closed.
- **Offers:** 14 total, **all terminal** (3 accepted, 1 rejected, 6 expired, 4 withdrawn). No live negotiation exists.
- Clubs 9 · agents 3 · mandates 17 · players 7,914.

The player catalogue is genuinely impressive and real. The transactional layer on top of it is empty. An investor sees a beautiful market and then a product that appears never to have done a transfer.

> **Note on a conflicting claim:** one source review concluded these counts were "enough deal-history variety to show." They are not — completed and collapsed deals are terminal read-only records. Acting on that line would cancel the single highest-value pre-demo task.

**Recommendation:** build a seeded demo scenario with deals parked at *each* lifecycle stage so any stage can be opened live. Same work item as C2.

### C2. The entire demo dataset is one command from destruction, and unreproducible

**Blocks demo.**

The convincing dataset — 7,914 players, 11 leagues, world teams with crests, 2,229 valuations — exists **only in the local Docker Postgres volume**. There is no `pg_dump`, no committed snapshot, and no seed script. `docker compose down -v` destroys it permanently.

Rebuilding requires internet access, a valid API-Football key, and roughly 595 API requests. The available scripts (`create_user.py`, `create_superuser.py`, `populate_world_teams.py`, `sync_leagues.py`) rebuild reference data only — none creates clubs, listings, offers, or deals together. Every demo setup is manual and non-repeatable, and there is no "reset to a known good state" path if a demo run corrupts the data.

**Recommendation:** `pg_dump` the current database and commit the snapshot, then write `scripts/seed_demo.py` that layers the transactional scenario from C1 on top of it. Treat "reset demo data" as a first-class, re-runnable script so a failed demo is recoverable in seconds. **This and C1 are the same work item and together are the top priority.**

### C3. Anyone on the internet can claim any player's identity

**Blocks pilot.** The finding most likely to end a club conversation.

`POST /auth/register` is fully public and unauthenticated. Registering with `user_type: PLAYER` and any unclaimed `player_id` grants an immediate working session bound to that player's record. The only guard in `create_player_profile` (`backend/app/auth/service.py:181`) is first-come-first-served:

```python
# Reject if another user already claimed this player
existing = await db.execute(
    select(PlayerProfile).where(PlayerProfile.player_id == player_id)
)
```

**Verified live** — an anonymous request claiming a well-known striker's record returned `201 Created` with access and refresh tokens; `GET /players/me` then returned that player's full record. (Test account deleted immediately afterwards.)

This is tracked as TRA-143 "player identity claims aren't attested", but the live behaviour is materially worse than that description, for two reasons:

**It confers binding consent rights.** `player_consent_to_terms` (`backend/app/deals/router.py:803`) authorises the caller by exactly this check:

```python
if pp is None or pp.player_id != deal.player_id:
    raise HTTPException(status_code=403, detail="Not the player for this deal")
```

An impostor satisfies it. Personal-terms consent is the platform's record that *the player agreed to their own contract* — the artifact Legal points at in a dispute. It can currently be produced by whoever registered first.

**It weaponises the platform's own proxy rule.** The account-gated proxy rule ([`architecture/authentication-and-permissions.md`](./architecture/authentication-and-permissions.md)) says a mandated agent may act for a player *only when the player has no account*. Creating a fraudulent `PlayerProfile` therefore **locks the legitimate mandated agent out** of proxy consent. The impostor doesn't merely gain rights — they strip them from the real representative. A safeguard becomes an attack amplifier.

Related exposures on the same endpoint: anyone can self-register a **club** (immediately receiving a `ClubFinance` row and market access) or an **agent** with a self-declared licence number.

**Recommendation:** close self-service registration. The product decision recorded in project memory is already *"no self-registration UI — admin creates users via CLI"*, but `POST /auth/register`, the `/register` route, and the "Create an account" link on `frontend/src/pages/auth/LoginPage.tsx:107` are all still live — the decision was made and never enforced. At minimum remove the link and the player/club/agent self-registration paths; keep the existing invitation flow; require admin attestation for player claims.

### C4. Daily background jobs never fire, and the flagship differentiator runs on stale data

**Blocks demo and pilot.**

All scheduled jobs are registered as plain intervals with no explicit first-run time (`backend/app/main.py:167-176`):

```python
_scheduler.add_job(_valuation_compute_job, "interval", hours=24, id="valuation_compute")
```

APScheduler's interval trigger with no `next_run_time` schedules the first run at *now + interval*. **A 24-hour job therefore never runs unless the process stays up for 24 unbroken hours.** In development the API restarts constantly; in production, any deploy, crash, or rolling restart resets the clock.

| Job | Interval | Consequence when it never runs |
|---|---|---|
| `valuation_compute` | 24 h | Fair-value model silently stops updating |
| `enrichment_sync` | 24 h | External valuation/wage enrichment never refreshes |
| `approval_expiry` | 24 h | Pending spending approvals never expire |
| `expire_mandates` | 24 h | Agent mandates outlive their end date |
| `deal_sla` | 24 h | Deal SLA deadlines are never enforced |
| `client_alerts` | 6 h | Agent client alerts stop |

**Evidence this is already happening:** the most recent row in `player_valuations` was computed **2026-07-06** — over a month ago — despite a "daily" recompute.

The demo consequence is specific. The fair-value-vs-asking signal (TRA-91/TRA-92) is TransferX's flagship differentiator. Right now:

- Latest valuation: **2026-07-06**, a month stale.
- Coverage: **2,229 of 7,914 players (28%)** — 72% of the catalogue shows nothing.
- Confidence: **1,565 MEDIUM, 664 LOW, zero HIGH.**

Critically, the vendor sync on 2026-08-08 imported roughly **12,000 fresh stat snapshots across 11 leagues**, and none of it reached the valuation model because the recompute never ran. The freshness problem the previous session solved is invisible in the product. Documentation still attributes the absence of HIGH-confidence rows to stale stats; the stats are no longer stale, so that explanation is out of date and this scheduler bug is the real cause.

> Note: job *bodies* are individually well-written — each wraps its work in `try/except` with logging, so a failing job cannot take down the app. That robustness is real but irrelevant while the jobs never execute.

**Recommendation:** pass an explicit `next_run_time`, or use a `cron` trigger at a fixed hour, so jobs run promptly after startup on a wall-clock schedule rather than an uptime-relative one. Then trigger a valuation recompute manually before any demo — the staff recompute endpoint under `/valuation` already exists. Verify the resulting coverage and confidence before quoting numbers publicly.

---

### C5. Contracted professionals were shown as free agents — and could be signed for nothing

**Blocks demo and pilot. Found 2026-08-11 (after the original audit), now fixed — see [ADR 0003](./architecture/decisions/0003-player-status-distinguishes-external-clubs.md).**

`PlayerStatus` had only two values, and `normalize_player_status` derived it from the presence of a **TransferX** contract alone. Every vendor-imported player — i.e. essentially the whole catalogue — therefore stored as `FREE_AGENT`:

- **7,830 of 7,914** players were `FREE_AGENT`.
- **7,825** of those had a real-world club recorded (`team_name` / `world_team_id`).
- **5** were genuinely unattached.

Lamine Yamal rendered as *"MID · Free agent"* while simultaneously browsable under Barcelona. The badge used the **green `success`** variant, so the UI actively framed 7,825 contracted professionals as opportunities.

The severe part was not the label. `create_free_agent_deal` gated solely on `status != FREE_AGENT`, and its own docstring describes the path as *"no seller, no fee, no offer/bid negotiation pipeline."* With no transfer windows configured, `is_transfer_allowed()` returns `True`. **Any club user with `MARKET_WRITE` could sign Yamal, Haaland, or any of ~7,824 other contracted players for £0, instantly, with no counterparty and no approval.**

This was partially known and repeatedly worked around: `scouting/service.py` carried a display-layer override for exactly this, and at least three frontend components had equivalent guards. All of them patched read paths; none fixed the stored value, and none protected the write path.

Why the original audit missed it: the two spot-checks that would have caught it point away from each other. Browsing the market shows correct club names (the frontend overrides were doing their job), and the free-agent signing endpoint looks correct in isolation — its guard is genuinely right, given a trustworthy `status`. The defect only appears when you ask what `status` actually contains.

**Resolution:** third enum value `EXTERNAL`, migration `0063` backfilling by the same rule the service now uses, defence-in-depth rejection on the signing path, and the compensating overrides deleted rather than duplicated. Verified: 7,825 `EXTERNAL` / 84 `CONTRACTED` / 5 `FREE_AGENT`, zero contradictions; 435 backend tests passing including three new regression tests.

---

## High findings

### H1. List pages show a convincing "no data" state when the backend is down

**Blocks demo and pilot.**

`DealListPage`, `OfferInboxPage`, `SentOffersPage`, `MySalesPage`, `ShortlistListPage`, `NotificationsPage`, and the dashboard panels **never check `isError`** from TanStack Query — verified: zero occurrences across the list pages. With retries configured, a backend outage resolves into the page's empty state: "No deals yet", "No offers received".

To anyone watching, that is indistinguishable from *the product having no data* — the worst possible misreading during an investor demo, and directly compounding C1. Detail pages handle errors correctly; the list pages silently lie.

**Recommendation:** add an `isError` branch with an explicit error banner to each list page. Contained, mechanical fix.

### H2. Admin Health page has three dead links

**Blocks demo.**

`frontend/src/pages/admin/AdminHealthPage.tsx:24-29`:

```typescript
const CATEGORY_LINK: Record<string, (id: string) => string> = {
  deals:     (id) => `/deals/${id}`,          // correct
  sales:     (id) => `/market/sales/${id}`,   // dead — real route is /sales/:id
  players:   (id) => `/market/players/${id}`, // dead — real route is /players/market/:id
  contracts: (id) => `/market/players/${id}`, // dead — same
};
```

Three of four categories 404 on click. Only `deals` resolves. Note this is **three** broken entries, not two — `contracts` reuses the same broken players path and is easy to miss.

**Recommendation:** three string replacements.

### H3. No row locks on offer accept, deal completion, or instalment payment

**Blocks pilot.**

`accept_offer` (`backend/app/offers/service.py:319`) loads the offer via `_get_offer_or_404` with **no `with_for_update()`**, then checks status and creates a `Deal` while committing the buyer's reserved budget. Two concurrent accepts — a double-click, or two staff in two browsers — can both pass the status check and produce two `Deal` rows with a double budget commit.

The same absence applies to `advance_deal`'s `CONFIRMED → COMPLETED` transition (double finance settlement, two `Contract` rows) and `mark_instalment_paid` (double credit).

This is **not** a blanket gap: bids *are* correctly locked (`sales/service.py` uses `with_for_update()` in four places, including `skip_locked` variants) and `commit_budget` locks the finance row (`clubs/service.py:389`). The locking discipline is real but inconsistently applied — offers and deal completion were missed.

A single-presenter demo is unlikely to trigger these. They are, however, the top correctness bugs in the codebase and exactly what a club's technical evaluator would probe. From a Finance seat, "the numbers reconcile" is the whole point.

**Recommendation:** add `with_for_update()` to the offer, deal, and instalment loads on those three write paths.

### H4. Agent mandates activate with no player confirmation

**Blocks pilot.** Tracked as TRA-144; confirmed real.

`create_mandate` (`backend/app/mandates/service.py:60`) validates only that the agent doesn't already represent the player and that no conflicting exclusive mandate exists. The `Mandate` is created with no status argument, defaulting to `ACTIVE`. **The player is never asked.**

An agent can unilaterally declare representation of any of the 7,914 players and immediately gain the agent-negotiation seat on that player's deals. From the Player's seat this is the harm the platform elsewhere works hard to prevent — TRA-127 was fixed specifically to stop an agent inserting themselves into a deal uninvited, and this reaches the same outcome by a different door.

**Recommendation:** mandates should enter a `PENDING` state requiring player confirmation before conferring negotiation rights, with admin attestation as the fallback where the player has no account.

### H5. Verification status gates nothing

**Blocks pilot.**

`Club.verified`, `AgentProfile.verified`, and `PlayerProfile.verified` exist and are set by the admin approval flow in `verification/service.py`. Searching every enforcement path in `sales/`, `offers/`, and `deals/` returns **no read of these fields**. The only consumer anywhere is a display field (`players/router.py:284`).

An entirely unverified club can list players, bid, negotiate, and complete transfers with identical privileges to a verified one. Combined with C3 (anyone can self-register a club), "verified" signals nothing a counterparty can rely on — while *looking* like it does, which is worse than not having it.

**Recommendation:** decide what verification gates — at minimum listing players and placing bids — and enforce it. If unverified clubs are intentionally allowed to trade during early access, say so in the UI rather than showing an unearned badge.

### H6. No password reset flow

**Blocks pilot.**

The `auth` router exposes register, login, refresh, logout, invitation preview/accept, `/me`, and `PATCH /me/password` (change while authenticated). There is **no forgot-password or reset flow**, and no frontend route for one.

A pilot user who forgets their password is permanently locked out and needs an engineer with database access. Invisible in a scripted demo; a week-one support incident in any real trial. Compounds with M7 — a reset flow needs working email.

### H7. Deal stages can deadlock, requiring superuser intervention

**Blocks demo and pilot.**

Several states have no self-service escape:

- **Dangling mandate** — an `ACTIVE` mandate pointing at a deleted `AgentProfile` moves the deal to `AGENT_NEGOTIATION` with a nonexistent agent; every advance then fails with "No agent negotiation record found". The deal is stuck unless collapsed.
- **Silent agent** — `AGENT_NEGOTIATION` has no per-stage expiry. If the agent never submits terms, the club cannot advance; the only escape is collapsing the deal.
- **Failed medical** — verified at `deals/service.py:434-439`: a `FAILED` medical check blocks `PAPERWORK → CONFIRMED` on every attempt. This is correct and deliberate (TRA-61), but the only way to unstick it is staff editing the record back.
- **Personal-terms edit loop** — every edit resets consent to `PENDING`, so an agent repeatedly tweaking terms forces the player to re-consent each time.

**Demo implication:** have a superuser session logged in and ready throughout the demo. **Product implication:** at least the dangling-mandate case is a genuine defect rather than a policy choice, and the silent-agent case argues for extending the existing `deal_sla` concept to individual stages — which is itself currently inert (see C4).

### H8. Refreshing or deep-linking a market page silently downgrades you to the anonymous view

**Blocks demo and pilot.**

`store/auth.ts` keeps `accessToken` **in memory only** — just the refresh token is persisted (`localStorage`), and `isBootstrapping` covers the window where the app trades it for a fresh access token. `ProtectedRoute` waits for that window to close (`App.tsx:107-108` — `if (isBootstrapping) return <LoadingScreen />`). **`PublicRoute` does not**: it is `<AppShell>{children}</AppShell>` and nothing more (`App.tsx:96-98`).

So on a hard load of a public route, the page mounts and fires its queries while `accessToken` is still `null`. The request reaches a `get_optional_user` endpoint with no `Authorization` header, and the server correctly answers as if for an anonymous visitor. Nothing errors; the page just quietly renders less.

Verified against a running stack, same sale, same user, authenticated vs. anonymous:

| Field | Authenticated | On hard reload |
|---|---|---|
| `fair_value_signal` | present | **null** |
| `bid_count` | 0 | **null** |

`reserve_price` and `best_bid` come from the same `viewer_club_id` gate in `_enrich_sale_response` (TRA-139), so a seller refreshing their own auction loses their reserve price and the bidding figures too.

Ten routes are affected — the entire market browse surface: `/players/market`, `/players/market/:id`, `/sales`, `/sales/:id`, `/clubs`, `/clubs/:id`, `/world/teams/:id`, `/transfers`, `/compare`.

**Demo implication:** never refresh the page mid-demo, and never paste a market link into a fresh tab — both produce a visibly poorer product than clicking to the same screen. This is easy to hit by accident and hard to explain in the moment.

**Recommendation:** gate `PublicRoute` on `isBootstrapping` the same way `ProtectedRoute` does, but only when a refresh token exists — an anonymous visitor with no token must not be made to wait. Contained fix in `App.tsx`.

### H9. The frontend type check has been passing without checking anything

**Blocks pilot.** Found 2026-08-13 while verifying a commit split, not by an audit sweep.

`npx tsc --noEmit` — the command used to verify "types are clean" throughout this project's sessions — resolves the **root** `frontend/tsconfig.json`, which is a project-references stub:

```json
{ "files": [], "references": [{ "path": "./tsconfig.app.json" }, { "path": "./tsconfig.node.json" }] }
```

With `"files": []` and no `-b`, TypeScript type-checks an empty file set and exits `0`. It has never once inspected `src/`. The project's own build script gets this right — `package.json` runs `tsc -b && vite build` — so **CI and production builds were never fooled**; only the ad-hoc verification command was.

Run correctly (`npx tsc -b --noEmit --force`), the codebase reports **44 errors** across 24 files. Verified as pre-existing by stashing all working changes and re-running against clean history: still 44, with and without `--force`. They fall into four groups:

- **Real type mismatches in app code** (`TS2322` ×15, `TS2339` ×8 = 23) — the ones that matter. `AdminPlayerDetailPage` reads `Player.contracts`, which does not exist on that type; `AdminDealsPage` reads `AdminDeal.updated_at`, likewise; several admin/club pages pass an `Element` where a `string` is required. These are places where the code and its types genuinely disagree, and where the compiler would have objected all along.
- **Unused declarations** (`TS6133` ×14) — dead imports and variables. Harmless, mechanical to clear.
- **Test-fixture drift** (`TS2550` ×3, `TS2740` ×2 = 5) — `PlayerCard.test.tsx` and `StatsPanel.test.tsx` build fixtures missing fields the real types now require, and `PlayerFilters.test.tsx` calls `Array.prototype.at` against an ES2021 lib target.
- **Missing Node types** (`TS2580`, `TS2304` = 2) — `process` in `vite.config.ts` and `global` in `test/setup.ts`. One `npm i -D @types/node` plus a `global` → `globalThis` edit; the cheapest two of the 44.

> **Correction, 2026-08-13:** this section first recorded **47**. That was a miscount — a clean forced run on the same commit gives 44, and the per-code tally above sums to exactly 44. The conclusion about the *command* is unaffected; only the figure was wrong.

**Implication beyond the errors themselves:** every "tsc clean" claim made in this project's session summaries and commit messages before 2026-08-13 was produced by this command and is therefore void as evidence. It was never a false claim about the *build* — `tsc -b` is what ships — but it was not the check it was believed to be. Correcting the record matters more than the 44 errors do.

**Recommendation:** use `npx tsc -b --noEmit` everywhere the old command appears, then triage the 44 as deliberate separate work — the 23 real mismatches first, since those indicate code and types actually disagreeing. Consider adding the correct invocation to CI so the check cannot silently no-op again.

---

## Medium findings

### M1. Two Accept-bid affordances on one page, one unguarded

`SaleDetailPage` renders **both** paths to the same irreversible action:

- **Guarded** (`SaleDetailPage.tsx:271-285`): checks `canMarketWrite` and opens a confirmation dialog naming the amount and buying club.
- **Unguarded** (`SellerOrderBook.tsx:162-172`, rendered at `SaleDetailPage.tsx:139`): a bare `Accept` button calling `acceptBidMutation.mutate(entry.id)` on click — **no confirmation, no capability check**.

A seller can accept a multi-million-pound bid with one unconfirmed click — the consumer-app pattern [`product-principles`](../.claude/skills/product-principles/SKILL.md) explicitly warns against. And because the order-book button skips the capability check, `SCOUT`/`READONLY` staff see an Accept button they cannot use; the backend correctly rejects it (`_market_write` is enforced), so this is a UX defect rather than a security hole — but it produces a live permission error in a demo and contradicts the documented "buttons hide, never disable" convention.

The security boundary holds. The inconsistency is the problem.

### M2. "Rumors coming soon" placeholder on the public transfers page

`frontend/src/pages/transfers/TransferActivityPage.tsx:450-458` renders a dashed-outline card reading "Rumors coming soon / Unconfirmed transfer links and market speculation will appear here."

This is the only visibly unfinished feature reachable by a non-admin user, on a **public** page — the single strongest "this isn't done" signal in the UI. Hide the section until it's implemented.

### M3. Console noise in production builds

Two verified issues:

- `LoginPage.tsx:28` — `console.error("Login error:", err)` fires on **every** failed login. A mistyped password prints a red stack trace; if the presenter has DevTools open, a typo looks like a crash.
- `lib/api.ts:16` — `console.log("[api] baseURL =", _baseURL)` runs at **module scope**, so it executes in the production bundle on every page load.

Gate both behind `import.meta.env.DEV`.

### M4. WebSocket reconnection has no UI feedback

`useWebSocket.ts` reconnects with exponential backoff capped at 30s (`backoffRef`, `ws.onclose` at line 106), correctly declining to retry on auth failure (4001). But no connection state is exposed to the UI.

If the socket drops mid-demo, live bid and deal updates stop and the presenter has no signal — pages simply look stale, and the natural reaction is to click around a product that appears frozen. A small "reconnecting" badge would remove the risk.

### M5. Analytics flush URL is broken in the built bundle

`lib/analytics.ts:55` posts to a hardcoded relative path:

```typescript
await fetch("/api/analytics/events", { ... })
```

This works under the Vite dev proxy. In the Docker `serve -s dist` build it resolves against the SPA's own origin, which returns `index.html` with a `200` — so failures are invisible and **all analytics are silently lost**. `lib/api.ts` already derives a correct base URL; this call bypasses it.

No user-facing impact, but the admin analytics view will show nothing, which is itself awkward if surfaced during a demo.

### M6. Bare `except Exception: pass` swallows vendor API failures

`backend/app/players/router.py` (two sites, ~lines 449 and 516) wraps external API calls in bare `except Exception: pass`. If the API-Football key is invalid or the vendor is down, the player detail page silently serves stale or empty transfer/injury data with no signal to anyone.

Given that a silent vendor-sync failure went undetected for a long period (the timezone crash fixed in the previous session), suppressing these errors entirely is the pattern most likely to hide the next one. Log at minimum.

### M7. Email sending is disabled by default

`smtp_host` defaults to `None`, disabling sending (`backend/app/config.py:116`). Staff invitations, notifications, and any future password reset **do not arrive**. The invitation flow has a deliberate mitigation — the raw link is returned once in the create response (spec decision D6) — so the flow is demonstrable, but "your Sporting Director gets an email" is not currently true.

The graceful no-op is well-implemented and won't error; the gap is only that nothing is delivered.

### M8. Money fields accept negative values

`deals/schemas.py` carries no `gt=0`/`ge=0` constraints on instalment amounts, clause values, or wages. Negative money can be written through the API. Not reachable through normal UI use, but it's the kind of thing a club's technical evaluator probes, and it undermines the "numbers reconcile" story that Finance cares about.

### M9. Player profile save gives no error feedback

`PlayerProfilePage.tsx:164-173` wraps `api.patch("/players/me", …)` in `try/finally` — so the spinner correctly stops — but there is **no `catch`**. A failed save produces an unhandled rejection and *zero* user-visible feedback: the form simply appears to do nothing. This is the only mutation in the frontend that bypasses the React Query `onError` → toast pattern.

### M10. No rate limiting on registration

The AI endpoints have a proper per-user sliding-window limiter (`backend/app/ai/rate_limit.py`); `POST /auth/register` has none. If a demo URL is shared, the endpoint is open to account spam. Largely moot once C3's recommendation (closing self-registration) lands.

### M11. 23 failing frontend tests — all stale, no product bugs

Both reviews independently reached the identical diagnosis. Every failure is a stale test:

| File | Failures | Cause |
|---|---|---|
| `PlayerCard.test.tsx` | 13 | `useCompare must be used inside CompareProvider` — component gained a context dependency; tests never wrapped in the provider |
| `PlayerFilters.test.tsx` | 7 | Queries for controls the redesigned UI renamed ("All positions", "Clear all", "Min age") |
| `StatsPanel.test.tsx` | 2 | Assertions against changed copy |
| `badges.test.ts` | 1 | Expects `"Confirmed"`; label deliberately changed to `"Ready to Execute"` |

**Good news:** not bugs. Backend is fully green at 403 passing, TypeScript clean. **Bad news:** a permanently red suite trains everyone to ignore it, so it won't catch the next real regression — and the three vendor-sync fixes from the previous session still have no regression coverage at all.

[`engineering/testing-strategy.md`](./engineering/testing-strategy.md) is stale on these numbers: it claims 19 backend files / 274 tests and 8 frontend files; actual is 26 backend files / 403 tests and 9 frontend files.

---

## Low findings

| ID | Finding | Location |
|---|---|---|
| L1 | Duplicate `QueryClient` instantiated in both files — harmless but confusing | `main.tsx:7`, `App.tsx:147` |
| L2 | Login doesn't restore the original URL — a deep link lands on the role home instead of the target | auth redirect flow |
| L3 | Business documentation is TODO stubs — cannot answer "what's the business model?" | `business/vision.md`, `business-model.md`, `target-users-and-market.md` |
| L4 | No production deployment story — investors will ask about hosting and scaling | `operations/environments-and-deployment.md` |
| L5 | `testing-strategy.md` coverage counts stale (see M11) | `engineering/testing-strategy.md` |
| L6 | No ERD or workflow diagrams — every diagram is a `TODO[Diagram not yet created]` placeholder | multiple docs |
| L7 | Pydantic `EmailStr` rejects `.local` TLDs — `dev@transferx.local` can never log in | already noted in `SESSION_HANDOVER.md` |
| L8 | `frontend-architecture.md` and `coding-standards.md` are stale/mostly TODO | `architecture/`, `engineering/` |
| L9 | Fixture data predates Aug 2026, so "next fixtures" surfaces look empty | fixtures cache |
| L10 | Unreachable duplicate `NotificationPreferencesPage` (redirected to `/account`) | dead code |

## Corrections — claims that did not survive verification

Recorded so they aren't re-derived later. Each was checked directly.

| Claim | Verdict |
|---|---|
| "Background jobs are solid — all 9 wrap their bodies in try/except, a failing job can't take down the app" | **Misleading.** The error handling is real, but the jobs **never execute** (C4). Robustness of code that doesn't run is not a strength. |
| "3 sales, 4 deals, 14 offers already in the live DB — enough deal-history variety to show" | **Wrong.** All four deals are terminal (3 completed, 1 collapsed) and all 14 offers are terminal. Nothing in progress exists to demonstrate (C1). |
| "`PlayerProfilePage.handleSave` has no try/catch" | **Inaccurate.** It has `try/finally`. The real defect is the missing `catch`/toast (M9); the "spinner stops" behaviour cited as the bug is the `finally` working correctly. |
| "litellm not installed — app won't start outside Docker" (listed as a blocker) | **Overstated.** `litellm>=1.0` is a declared dependency (`backend/pyproject.toml:23`). A stale local virtualenv is an environment issue, not a code defect, and Docker — how this project actually runs — is unaffected. |
| "AdminHealthPage — two string replacements" | **Undercounted.** Three entries are dead: `sales`, `players`, and `contracts` (H2). |
| Player identity attestation rated *medium*, as a restatement of TRA-143 | **Under-severity.** Live testing shows it confers binding personal-terms consent and inverts the proxy rule to lock out the legitimate mandated agent (C3). |

## What is genuinely demo-ready

An audit that only lists problems misrepresents the product. These held up under direct inspection and are worth leading with:

- **The permissions and confidentiality model is the strongest part of the system.** The capability matrix is genuinely single-source (`clubs/capabilities.py`), consumed by the frontend rather than re-derived, and enforced at every club write route. Field-level scoping keeps commission terms from the player and each club's position from the other. The backend correctly rejected the capability bypass probed in M1.
- **The deal stage machine is well-designed** — guards at every transition, a medical-check gate, budget release on collapse, and correct locking on the bid path.
- **The audit trail is comprehensive and actor-attributed** — every deal-mutating action emits an event with a resolved actor label, exposed as JSON and CSV, scoped to participants. Exactly what a Sporting Director means by "an audit trail I can point to in a dispute."
- **Consent is structurally enforced** — every deal routes through `PERSONAL_TERMS` regardless of agent involvement (TRA-60, [ADR 0002](./product/decisions/0002-single-capture-point-for-personal-terms.md)). The design is right; C3 attacks *who* can consent, not whether consent is required.
- **The API client is excellent** — single-flight silent token refresh on 401, network-error detection distinguished from bad credentials on login.
- **App-level React error boundary** with a graceful "Something went wrong / Reload" card.
- **Real market data at real scale** — 7,914 players across 11 leagues with photos, crests, stats, and form scores.
- **The build is healthy** — 403 backend tests green, TypeScript clean, migrations auto-applied on startup with a clean linear chain to `0059`, no runtime errors in API logs.
- **Sensible defaults elsewhere** — no transfer windows configured means the market is open (won't block a demo); email no-ops gracefully rather than erroring.
- **Data integrity under vendor sync is principled** — [ADR 0001](./architecture/decisions/0001-vendor-data-never-overrides-transferx-contract.md) establishes that vendor data never overrides a TransferX contract, verified against a live contracted player.

## Recommended pre-demo sequence

Ordered by return on effort. Items 1–5 are what actually change the demo outcome.

| # | Fix | Findings | Effort |
|---|---|---|---|
| 1 | `pg_dump` snapshot + `scripts/seed_demo.py` creating deals at **every** lifecycle stage | C1, C2 | Medium |
| 2 | Fix scheduler first-run time, then recompute valuations and verify coverage | C4 | Small |
| 3 | Close self-registration — remove the link, route, and player/club/agent paths | C3, M10 | Small |
| 4 | Add `isError` branches to all list pages | H1 | Medium |
| 5 | Fix the three AdminHealthPage links; remove the "Rumors coming soon" card | H2, M2 | Trivial |
| 6 | Add row locks to offer accept, deal completion, instalment payment | H3 | Small |
| 7 | Route order-book Accept through confirm + capability; add `catch`/toast to profile save | M1, M9 | Small |
| 8 | Gate console output behind `DEV`; fix analytics base URL; log vendor failures | M3, M5, M6 | Trivial |
| 9 | Have a superuser session ready during the demo for stage-deadlock recovery | H7 | Process |
| 10 | Decide and enforce what verification gates; put mandates behind player confirmation | H4, H5 | Medium |
| 11 | Repair the 23 stale frontend tests; add regression coverage for the vendor-sync fixes | M11 | Medium |
| 12 | Password reset + working SMTP before any real trial; write the business vision doc | H6, M7, L3 | Medium |

Items 1–8 are the minimum viable demo preparation — roughly one to two days for an engineer who knows the codebase. Items 9–12 are pilot preparation.

## Related documents

- [`IMPLEMENTATION_STATUS.md`](./IMPLEMENTATION_STATUS.md) — verified build status; findings here that get fixed belong there
- [`security-and-compliance/permissions-model.md`](./security-and-compliance/permissions-model.md) — where C3, H4, and H5 belong once resolved
- [`architecture/authentication-and-permissions.md`](./architecture/authentication-and-permissions.md) — the capability model M1 is inconsistent with
- [`product/workflows/transfer-lifecycle.md`](./product/workflows/transfer-lifecycle.md) — the lifecycle C1 says cannot currently be demonstrated
- [`SESSION_HANDOVER.md`](./SESSION_HANDOVER.md) — current handover context
