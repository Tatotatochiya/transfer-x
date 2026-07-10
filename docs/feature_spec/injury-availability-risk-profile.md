---
title: "Feature Spec: Injury-Availability Risk Profile"
last_updated: 2026-07-05
status: Active
owner: "TODO — assign a Product Owner"
---

# Feature Spec: Injury-Availability Risk Profile

## Purpose

Full implementation specification for turning TransferX's already-ingested injury history (`PlayerInjury`, fed by API-Football `/sidelined`) from a passive list into a decision-support signal: an **availability percentage**, a **risk band**, and a **recurrence flag**, surfaced at the points where clubs decide — player cards, player/sale detail, and the deal room — alongside the fair-value signal ([sibling spec](./fair-value-vs-asking-signal.md)).

"Availability is the best ability" is a real recruitment axiom: *"Model £19m"* next to *"missed 25% of the last two seasons"* is a stronger decision artifact than either alone.

There is **no Linear ticket for this feature yet** — it was proposed and accepted in the 2026-07-05 working session as a differentiator not covered by the existing backlog. See [Linear reconciliation](#linear-reconciliation-suggested-not-executed).

This document is written for an implementer (human or AI agent) with **no access to the conversation that produced it**.

## How to use this document

1. Read [Decisions already made](#decisions-already-made) and the **[ingestion findings](#data-inputs-verified-against-code-2026-07-05)** first — the current ingestion silently discards the field this feature needs most, and the spec includes the fix.
2. Implement the ingestion change, then the engine/API per [The model](#the-model--exact-specification) and [Backend implementation](#backend-implementation), then [UI](#ui-specification).
3. Verify against [Success criteria](#success-criteria) — the worked examples are exact fixtures.
4. On completion, follow [Definition of done](#7-definition-of-done--tests-and-documentation) and set this spec's `status` to `Implemented`.

Read before coding: repo `CLAUDE.md`, [`engineering-standards`](../../.claude/skills/engineering-standards/SKILL.md), [`product-principles`](../../.claude/skills/product-principles/SKILL.md), and the [gotchas appendix](#appendix-implementation-gotchas-house-specific).

## Product context and value

| Stakeholder | Value |
|---|---|
| Buying club / Sporting Director | Availability risk visible at the decision point, before committing a fee and a wage to a player who may miss a third of the season. |
| Selling club | Symmetric: a clean availability record is a *selling* point, shown automatically. |
| Agent | Represents clients honestly — a clean record strengthens their pitch; a flagged one lets them pre-empt the conversation. |
| Finance | Wages paid to sidelined players are pure cost; availability quantifies that exposure before signing. |

**Hard confidentiality boundary (see D5):** this profile is derived exclusively from *publicly recorded* vendor absence data. It is **not** a medical assessment and must never mix with, imply, or leak the deal's `MedicalCheck` record (staff-written, participant-confidential — see [permissions-model](../security-and-compliance/permissions-model.md)). The mandatory UI disclaimer exists for exactly this reason.

## Scope

### In scope (v1)

- Ingestion fix: capture the sidelined spell's **end date** (currently discarded — see findings).
- A deterministic, interpretable risk engine over absence spells: availability %, risk score/band, recurrence detection, ongoing-spell flag.
- Compute-on-read API (single + batch) — no new persistence table, no scheduled job.
- UI: risk badge on cards (elevated risk only), availability strip on player/sale detail above the existing `InjuryHistoryPanel`, one line in the deal room next to the fair-value strip, breakdown popover.

### Explicitly out of scope (v1)

| Deferred item | Why | Tracked |
|---|---|---|
| Soft-tissue vs impact injury classification | `injury_type` is a free-text vendor string; keyword taxonomies are a refinement, not a foundation. Recurrence detection (exact-type repeats) covers the headline case. | Future ticket if v1 proves out |
| Discipline/suspension signal | Suspensions are excluded from this profile (D4); a separate "availability lost to discipline" signal is a different product question. | Not tracked |
| Composite "value per available minute" | Natural pairing with the fair-value signal once both are shipped. | Future ticket |
| Injury-adjusted fair value | The fair-value model deliberately does not consume this signal in v1 — two independent, interpretable signals beat one entangled one at demo stage. | Future model version |
| Per-league match-calendar denominators | Day-based rates (D2) avoid inventing games-per-season constants per competition. | — |

## Decisions already made

Settled 2026-07-05. Do not reverse silently — surface any conflict per [`engineering-standards`](../../.claude/skills/engineering-standards/SKILL.md) §4.

- **D1 — Score on days missed, not games missed.** Verified 2026-07-05: the vendor's `/sidelined` records are `{type, start, end}`; the current ingestion stores `start` (as `fixture_date`) and **discards `end`**, while `games_absent` and `season` are hardcoded `None` on every row (`players/router.py`). Any games-based formula would run on always-null columns and silently score everyone zero. Days between start and end is what the vendor actually provides; v1 captures and scores on that.
- **D2 — Rolling day-rate window, no per-season game constants.** The window is the current season plus two prior (season = July 1–June 30, labelled by starting year, matching API-Football's convention). All rates are `days / window_days` — no invented "38-game season" denominators, no league-calendar tables.
- **D3 — Never fabricate a duration.** A spell with no end date is either *ongoing* (started ≤ 120 days before `as_of` → counted as `as_of − start` days, flagged) or *unrecorded* (older → excluded from day sums, counted as a spell, degrades confidence). If more than 25% of counted spells are unrecorded, **no numeric score is produced at all** (`INCOMPLETE` status). A fabricated LOW risk on an unrecorded cruciate injury would be this feature's worst possible failure.
- **D4 — Suspensions are excluded.** Discipline is not fitness. Spells whose `injury_type` case-insensitively contains any of `{"suspend", "red card", "yellow card", "ban"}` (a tunable constant) are filtered out before any computation.
- **D5 — Strict separation from the deal `MedicalCheck`.** Different data, different confidentiality class, different owner. The profile never reads, implies, or displays anything from `MedicalCheck`; the UI disclaimer is mandatory on every breakdown surface.
- **D6 — Player accounts are excluded (403), consistent with the fair-value spec's D6.** The signal is club/agent decision-support; the raw injury *history* endpoint stays as-is for all authenticated users.
- **D7 — "No rows" is ambiguous and must not silently mean "clean."** The sync is lazy delete-and-rewrite with no marker when it returns empty. Therefore: the **single** profile endpoint refreshes from the vendor first, so an empty result is *verified* clean and rendered as such; the **batch** endpoint never refreshes (50 vendor calls per grid page is not acceptable) and simply omits row-less players — cards show elevated-risk badges only, and absence of a badge claims nothing.
- **D8 — Compute-on-read, no persistence.** The profile is derived from a handful of rows that are themselves the audit trail; a table, migration for profiles, and daily job would be speculative. `model_version` (`"injury-v1"`) travels in the response payload only.

## Data inputs (verified against code, 2026-07-05)

| Input | Source | Verified state |
|---|---|---|
| Absence spells | `app/players/models.py::PlayerInjury` — `injury_type`, `fixture_date` (= spell **start**), `reason`, `games_absent`, `season`, `fetched_at` | Rows are written only by the lazy refresh inside `players/router.py::get_player_injuries` (24h cache via `CAREER_CACHE_HOURS`, delete-and-rewrite per player). **`games_absent` and `season` are hardcoded `None`; the API's `end` date is parsed nowhere; `reason` is read from a key the documented payload doesn't contain — treat all three as absent.** |
| Spell end date | API-Football `/sidelined` response: `{"type", "start", "end"}` (`vendor/client.py::get_player_sidelined`) | **Available from the vendor, currently discarded.** Captured by this feature (new `end_date` column). |
| Player identity/visibility | `Player.vendor_id` (required for refresh), visibility rule in `players/router.py::player_market_detail` | PRIVATE → 404 unless creator; CLUBS_ONLY → auth required. |
| Existing UI | `frontend/src/components/players/InjuryHistoryPanel.tsx` | Passive chronological list; kept, with the new strip rendered above it. |

**Pre-existing gap discovered while verifying (flag, do not silently fix in this feature):** `GET /players/market/{player_id}/injuries` requires only authentication and does **not** apply the PRIVATE-player visibility check that `player_market_detail` enforces. The new profile endpoints below *do* enforce it; the existing injuries endpoint should get its own small fix — see [Linear reconciliation](#linear-reconciliation-suggested-not-executed).

## The model — exact specification

Deterministic and pure: the engine takes the spell list and an explicit `as_of` date — same inputs ⇒ same outputs, and tests pin `as_of`.

### Stage 0 — Window

- `current_season_start` = July 1 of (`as_of.year` if `as_of` ≥ July 1 else `as_of.year − 1`).
- `window_start` = `current_season_start` minus 2 years. `window_days` = `(as_of − window_start).days`.
- Example: `as_of` 2026-07-05 → window 2024-07-01 → 2026-07-05, `window_days` = **734**.

### Stage 1 — Spell preparation

From the player's `PlayerInjury` rows:

1. **Filter suspensions** (D4): drop rows whose `injury_type` contains a suspension term (case-insensitive).
2. **Parse dates**: `start` = `fixture_date`; `end` = `end_date` (new column). Rows with no parseable `start` are excluded from all day sums and counted as *unrecorded* spells.
3. **Classify each remaining spell**:
   - `end` present → *closed*: `days = (end − start).days` (return day exclusive; negative/zero → treat as unrecorded).
   - `end` null and `start` ≥ `as_of − 120 days` → *ongoing*: `days = (as_of − start).days`, profile carries an `ongoing_spell` flag.
   - `end` null and older → *unrecorded*: no day count.
4. **Clip to window**: a spell's counted days are the days of its `[start, end)` interval intersected with `[window_start, as_of)`. Spells entirely before `window_start` are ignored (they don't count as spells either).

Let `spells` = closed + ongoing + unrecorded spells intersecting the window; `unrecorded_share = unrecorded / spells`.

### Stage 2 — Integrity gate

- `spells == 0` → **clean profile**: availability 100.0%, risk score 0.0, band LOW. (Only reachable as "verified clean" via the refresh path — D7.)
- `unrecorded_share > 0.25` → **`INCOMPLETE`**: no score, no availability; response carries `spell_count` and `unrecorded_spells` so the UI can say what's known.
- Otherwise → compute Stages 3–5. `unrecorded_share > 0` (but ≤ 0.25) caps confidence at MEDIUM; `> 0.10` caps at LOW? — no: exact rule in Stage 5.

### Stage 3 — Availability

```
availability_pct = (1 − counted_missed_days / window_days) × 100      # rounded to 1 dp
```

`counted_missed_days` = Σ window-clipped days of closed + ongoing spells.

### Stage 4 — Risk score (0–100, higher = more risk)

| Component | Definition | Norm | Weight |
|---|---|---|---|
| Absence burden | `burden_rate = counted_missed_days / window_days` | `clamp(burden_rate / 0.25, 0, 1)` — 25%+ of the calendar sidelined maxes it | 45 |
| Recurrence | `repeat_spells = spells − distinct_types` (types compared case-folded/stripped; unrecorded spells count in both terms) | `clamp(repeat_spells / 3, 0, 1)` | 30 |
| Recency | `recent_rate = days missed in [as_of − 365, as_of) / 365` (window-clipped, closed + ongoing) | `clamp(recent_rate / 0.25, 0, 1)` | 25 |

`risk_score = Σ (weight × norm)`, rounded to 1 dp.

**Bands:** `LOW` < 20 ≤ `MODERATE` < 45 ≤ `ELEVATED` < 70 ≤ `HIGH` (boundaries belong to the higher band).

**Recurrence display list:** every normalized type with count ≥ 2, e.g. `[{"type": "Hamstring", "count": 3}]`. Known v1 limitation (accepted): "Hamstring" and "Hamstring Injury" are distinct strings and won't group — keyword grouping is deferred (out-of-scope table).

### Stage 5 — Confidence

| Level | Rule |
|---|---|
| HIGH | `unrecorded_spells == 0` |
| MEDIUM | `unrecorded_share ≤ 0.25` (and > 0) |
| LOW | never reached with a score in v1 (higher shares are `INCOMPLETE`) — reserved for future relaxation |

All constants above (window years, 120-day ongoing cutoff, 0.25 caps and shares, weights, bands, suspension terms) live in one constants module and are tunable; the worked examples are the regression net for any tuning.

### Worked examples — exact test fixtures

`as_of` pinned to **2026-07-05** (window 2024-07-01 → 2026-07-05, 734 days). Tolerances: day counts exact; `risk_score` ± 0.2; `availability_pct` ± 0.2 pp.

#### Example A — recurrent hamstring, high burden

Spells (type, start → end):

| # | Type | Start | End | Days |
|---|---|---|---|---|
| 1 | Hamstring | 2024-09-10 | 2024-10-22 | 42 |
| 2 | Hamstring | 2025-02-01 | 2025-03-15 | 42 |
| 3 | Knock | 2025-04-20 | 2025-04-27 | 7 |
| 4 | Hamstring | 2025-11-08 | 2026-01-10 | 63 |
| 5 | Ankle Sprain | 2026-03-02 | 2026-03-30 | 28 |

- `counted_missed_days` = 182; `burden_rate` = 182/734 = 0.24796 → norm 0.99183 → contribution **44.63**
- 5 spells, 3 distinct types → `repeat_spells` = 2 → norm 0.66667 → contribution **20.00**
- last-365 days (from 2025-07-05): spells 4+5 = 91 days → `recent_rate` 0.24932 → norm 0.99726 → contribution **24.93**
- `risk_score` = **89.6** → band **HIGH**; `availability_pct` = **75.2%**; recurrences `[Hamstring × 3]`; confidence **HIGH**.

#### Example B — one knock in two years

One spell: Knock, 2024-11-03 → 2024-11-10 (7 days).

- burden 7/734 = 0.00954 → contribution 1.72; recurrence 0; recency 0 (spell predates last-365 window)
- `risk_score` = **1.7** → **LOW**; `availability_pct` = **99.0%**; confidence **HIGH**.

#### Example C — incomplete records (no score)

Rows: Cruciate Ligament Injury, start 2025-10-14, end **null** (264 days before `as_of` → older than the 120-day ongoing cutoff → *unrecorded*); Suspended, 2026-02-01 → 2026-02-15 (**filtered**, D4).

- `spells` = 1, `unrecorded` = 1 → share 1.0 > 0.25 → status **`INCOMPLETE`**: no `risk_score`, no `availability_pct`; `spell_count` 1, `unrecorded_spells` 1.
- UI renders: *"Injury records incomplete — 1 recorded absence with unrecorded duration."* Never a LOW badge — an unrecorded cruciate injury scored as healthy is exactly what D3 forbids.

## Backend implementation

### Part 1 — Ingestion fix (prerequisite)

1. **Migration**: add `end_date: Mapped[date | None]` to `PlayerInjury` (`Date`, nullable). Use the next available migration number — the head is `0047_agent_negotiation_commission_only` as of 2026-07-05, but the [fair-value spec](./fair-value-vs-asking-signal.md) also allocates the next slot; check `backend/migrations/versions/` and chain `down_revision` off the actual current head at implementation time.
2. **Populate it**: in the refresh logic, `end_date` from `s.get("end")` (same date-parse guard as `start`). No data backfill needed — the existing 24h delete-and-rewrite cache repopulates a player's rows, now with end dates, on next view.
3. **Extract the refresh** out of `players/router.py::get_player_injuries` into `players_service.refresh_injury_history(db, player) -> bool` (returns whether a vendor fetch succeeded). Both the existing injuries endpoint and the new profile endpoint call it — one copy of the fetch/cache logic, per the reuse rule in [`engineering-standards`](../../.claude/skills/engineering-standards/SKILL.md). Preserve the existing swallow-and-serve-stale error behaviour.

### Part 2 — Profile engine and API

No new table, no job (D8). New files in the `players` module (the injury data's owner — no new top-level module):

| File | Contract |
|---|---|
| `app/players/injury_profile.py` | Constants block + **pure functions** (no DB imports): `build_profile(spells: list[SpellInput], as_of: date) -> InjuryProfile`. All stages above. Unit-testable without fixtures. |
| `app/players/service.py` | `get_injury_profile(db, player, *, refresh: bool)` — optionally `refresh_injury_history` first (single endpoint: yes; batch: no), load rows, call engine with `as_of = date.today()`; `get_injury_profiles(db, player_ids)` — one query for all rows (no N+1), engine per player, omit row-less players (D7). |
| `app/players/schemas.py` | `InjuryProfileResponse` (shape below), status enum `OK / INCOMPLETE / UNAVAILABLE`, band + confidence enums. |
| `app/players/router.py` | Two endpoints below, styled after the existing `/market/{player_id}/injuries` route. |

### API contract

Authentication required on both; **`user_type == PLAYER` → 403** (D6). Both enforce the PRIVATE-player visibility rule from `player_market_detail` (unlike the current injuries endpoint — see the flagged gap).

**`GET /players/market/{player_id}/injury-profile`** — refreshes first (D7), then computes. 200:

```json
{
  "player_id": "5f0c…",
  "status": "OK",
  "risk_score": 89.6,
  "risk_band": "HIGH",
  "availability_pct": 75.2,
  "days_missed_window": 182,
  "window_days": 734,
  "window_start": "2024-07-01",
  "spell_count": 5,
  "unrecorded_spells": 0,
  "recurrences": [{"type": "Hamstring", "count": 3}],
  "ongoing_spell": null,
  "confidence": "HIGH",
  "model_version": "injury-v1",
  "as_of": "2026-07-05",
  "components": [
    {"label": "Absence burden", "detail": "182 of 734 days", "norm": 0.992, "weight": 45, "contribution": 44.6},
    {"label": "Recent absences", "detail": "91 days in the last year", "norm": 0.997, "weight": 25, "contribution": 24.9},
    {"label": "Recurrence", "detail": "2 repeat spells", "norm": 0.667, "weight": 30, "contribution": 20.0}
  ]
}
```

- `status: "INCOMPLETE"` → `risk_score`, `risk_band`, `availability_pct`, `components` all null; counts still present (Example C).
- `status: "UNAVAILABLE"` → everything null: player has no rows **and** no refresh was possible (no `vendor_id`, or no API key configured). Distinct from clean.
- Verified-clean (refresh ran, zero spells) → `status: "OK"`, score 0.0, band LOW, availability 100.0, `spell_count` 0.
- `ongoing_spell`, when set: `{"type": "Ankle Sprain", "since": "2026-06-20", "days_so_far": 15}`.
- 404: player not found or PRIVATE-invisible to caller.

**`GET /players/market/injury-profiles?ids=<uuid,…>`** — batch, cap 50 (else 422), **never refreshes**, silently omits row-less/invisible players (D7): `{"profiles": {"<player_id>": {…}}}`.

### Backend files-to-touch checklist

- [ ] `backend/app/players/models.py` — `end_date` column
- [ ] `backend/migrations/versions/` — next number, `end_date` only
- [ ] `backend/app/players/router.py` — populate `end_date`; extract refresh; two new endpoints
- [ ] `backend/app/players/service.py` — `refresh_injury_history`, profile orchestration
- [ ] `backend/app/players/injury_profile.py` (new) — constants + pure engine
- [ ] `backend/app/players/schemas.py` — response schemas
- [ ] `backend/tests/test_injury_profile.py` (new) — engine fixtures + endpoint tests

## UI specification

House system: dark theme, shared badge/panel idioms, TanStack Query. Types in `src/types/api.ts` / `enums.ts` (`InjuryProfile`, `InjuryRiskBand`, `InjuryProfileStatus`).

### Components (new)

**`InjuryRiskBadge`** — `frontend/src/components/players/InjuryRiskBadge.tsx`
- Props: `{ profile: InjuryProfile; compact?: boolean }`.
- Band colors (same language as `FairValueBadge`): LOW emerald-400 · MODERATE slate-400 · ELEVATED amber-400 · HIGH rose-400.
- `compact` (cards): pill `Injury risk: High` — rendered **only** for ELEVATED/HIGH (D7: grids flag risk, they don't certify health). Renders nothing otherwise.
- Full (detail pages): strip — `Availability 75.2% (last 2 seasons) · 182 days missed · Hamstring ×3 · High injury risk`, plus ongoing-spell suffix when present (`Currently sidelined — Ankle Sprain, 15 days`), confidence tag, info trigger → breakdown popover.

**`InjuryProfileBreakdown`** (popover) — the three `components` rows (label, detail, contribution), window dates, spell/unrecorded counts, `as_of`, and the **mandatory footer**: *"Derived from publicly recorded absences — not a medical assessment, and unrelated to any TransferX medical check."* (D5.)

### Surface-by-surface

| Surface | Change |
|---|---|
| `PlayerCard` (market grid) | Compact badge via the **batch** endpoint (one call per page); ELEVATED/HIGH only. |
| `PlayerMarketDetailPage` | Full strip rendered directly **above the existing `InjuryHistoryPanel`** (panel unchanged); single endpoint (refreshing). |
| `SaleDetailPage` | Same full strip in the player-info area. |
| `DealDetailPage` (deal room) | One line adjacent to the fair-value strip, club/agent/staff identities only (via `useIdentity`; server 403s player accounts regardless). |

### States

| State | Behaviour |
|---|---|
| `OK`, clean (0 spells) | Detail: `No recorded absences in the last 2 seasons · Availability 100%` in emerald. Cards: nothing. |
| `INCOMPLETE` | Detail: muted amber line — `Injury records incomplete — N absence(s) with unrecorded duration.` No score, no band, no availability figure anywhere. Cards: nothing. |
| `UNAVAILABLE` | Detail: muted `Injury history unavailable for this player.` Cards: nothing. |
| Ongoing spell | Strip suffix + rose dot; never extrapolate a return date. |
| Loading / error | Skeleton sized to the strip / render nothing — the profile is an enhancement and must never block the page. |
| Player-account viewer | Nothing rendered; no request issued. |

### Copy rules (mandatory)

Band phrases only: "Low injury risk" / "Moderate injury risk" / "Elevated injury risk" / "High injury risk". **Never** "injury-prone", "fragile", "crocked", or any medical/diagnostic phrasing ("unfit", "failed"). Always "recorded absences", never "medical record". The D5 disclaimer footer appears on every breakdown surface.

### Frontend files-to-touch checklist

- [ ] `src/types/api.ts`, `src/types/enums.ts`
- [ ] `src/components/players/InjuryRiskBadge.tsx` + `InjuryRiskBadge.test.tsx` (new)
- [ ] `src/components/players/InjuryProfileBreakdown.tsx` (new)
- [ ] `src/components/players/PlayerCard.tsx` — compact badge
- [ ] `src/pages/market/PlayerMarketDetailPage.tsx`, `src/pages/market/SaleDetailPage.tsx`, `src/pages/deals/DealDetailPage.tsx`
- [ ] Market grid — batch fetch wiring (share the pattern with the fair-value batch call if both land)

## Success criteria

### 1. Backend functional acceptance

- [ ] Ingestion captures `end_date` from the vendor `end` field; a re-viewed player's rows carry it.
- [ ] Refresh logic exists in exactly one place (`players_service.refresh_injury_history`), used by both endpoints.
- [ ] Single endpoint refreshes then computes; batch computes from rows only and omits row-less players.
- [ ] Engine is pure (no DB imports) and takes `as_of` explicitly.
- [ ] Zero-spells-after-verified-refresh returns the clean profile, not `UNAVAILABLE`.
- [ ] `INCOMPLETE` and `UNAVAILABLE` statuses returned per the contract, with all score fields null.

### 2. Reference fixtures

- [ ] Unit tests encode Examples A, B, C exactly (inputs → status/score/band/availability/recurrences, `as_of` pinned to 2026-07-05, tolerances as stated). These are the regression net for any constant tuning — update them in the same commit as any tuning, deliberately.

### 3. Edge-case matrix

| Input condition | Required behaviour |
|---|---|
| Spell with suspension term in type (any case) | Excluded from spells, days, recurrence — everywhere |
| `end` null, start 30 days before `as_of` | Ongoing: days = `as_of − start`, `ongoing_spell` set |
| `end` null, start 264 days before `as_of` | Unrecorded: no days, counts as spell, degrades confidence / trips `INCOMPLETE` |
| `end` ≤ `start` | Treated as unrecorded (bad vendor data, never negative days) |
| Unparseable/missing `start` | Excluded from sums, counts as unrecorded spell |
| Spell spanning `window_start` | Only in-window days counted |
| Spell entirely before window | Ignored completely (not a spell) |
| 4 spells, 1 unrecorded (25%) | Scored, confidence MEDIUM (share ≤ 0.25 boundary) |
| 3 spells, 1 unrecorded (33%) | `INCOMPLETE` |
| Exactly score 20 / 45 / 70 | Bands MODERATE / ELEVATED / HIGH (boundary → higher band) |
| PRIVATE player, non-creator | 404 on both endpoints |
| PLAYER-type account | 403 on both endpoints |
| No `vendor_id` / no API key, no rows | `UNAVAILABLE`, never clean |
| Batch with 51 ids | 422 |

### 4. Calibration sanity checklist (seeded dev data, before demo)

- [ ] A player with one short knock in two seasons lands LOW with availability ≥ 98%.
- [ ] A player sidelined ~50% of the window lands HIGH regardless of recurrence.
- [ ] No profile anywhere shows availability > 100% or < 0%, or a score outside [0, 100].
- [ ] Spot-check ~5 seeded players against their raw `InjuryHistoryPanel` list — strip and list must visibly agree (same spells, same story).

### 5. UI acceptance

- [ ] Detail page (fixture-A player): exact strip `Availability 75.2% (last 2 seasons) · 182 days missed · Hamstring ×3 · High injury risk` with rose styling; popover shows the three components and the mandatory disclaimer.
- [ ] Market grid: badges only on ELEVATED/HIGH players; one batch call per page; LOW/clean/absent players show nothing.
- [ ] Deal room: line renders for club/agent/staff; nothing for a player participant; no request issued for player identity.
- [ ] `INCOMPLETE` / `UNAVAILABLE` / clean / ongoing states render per the states table.
- [ ] `InjuryRiskBadge.test.tsx` covers: each band's label+color, compact-mode ELEVATED/HIGH-only rule, INCOMPLETE renders nothing (compact) / correct line (full), null profile renders nothing.

### 6. Non-functional

- [ ] Determinism: engine twice on identical inputs ⇒ identical outputs.
- [ ] Batch of 50 ⇒ one `PlayerInjury` query (no N+1); no vendor calls from batch.
- [ ] Permission tests: unauthenticated 401, player-account 403, PRIVATE 404.
- [ ] TypeScript clean; full backend suite green (274 baseline + new).

### 7. Definition of done — tests and documentation

Per [`documentation-standards`](../../.claude/skills/documentation-standards/SKILL.md), same session as implementation:

- [ ] `docs/CHANGELOG.md` — `Added` (profile) **and** `Fixed`/`Changed` (ingestion now captures spell end dates).
- [ ] `docs/IMPLEMENTATION_STATUS.md` — verified row.
- [ ] `docs/architecture/data-model.md` — `PlayerInjury` note (`end_date`).
- [ ] `docs/business/glossary.md` — "Availability (injury profile)" entry.
- [ ] This spec — `status: Implemented` + deviations note.
- [ ] Suggest (not execute) the Linear items below.

### 8. Demo script (end-to-end gate)

1. Seed a player with fixture-A's five spells and a FIXED_PRICE listing; a second player with fixture-B's record.
2. As a buying club: market grid shows a `High` badge on player A only.
3. Open player A's detail → strip + popover (components, disclaimer); `InjuryHistoryPanel` below tells the same story.
4. Open a deal on player A → availability line beside the fair-value strip.
5. Log in as the player on that deal → no line, and direct endpoint call → 403.
6. Open player B's detail → clean emerald state, no grid badge.
7. Corrupt one spell's end date to null (aged > 120 days) and re-view → `INCOMPLETE`, score gone — verifying D3 end to end.

## Future evolution

- **"Value per available minute"** — composite of this signal and the fair-value model once both are shipped and trusted separately.
- **Type grouping** — keyword taxonomy so "Hamstring" / "Hamstring Injury" recur together; soft-tissue weighting.
- **xG-vendor era** — if the future stats vendor (see the fair-value spec) carries structured injury data with reliable durations, swap the spell source behind the same engine; bump to `injury-v2`.

## Linear reconciliation (suggested, not executed)

Per [`linear-workflow`](../../.claude/skills/linear-workflow/SKILL.md) — suggestions only, no tickets created by this spec:

- **New feature ticket**: "Injury-availability risk profile" (backend + UI, or split per the project's backend/UI convention) under *Differentiation & Demo Readiness → Key selling points*, linking this spec. No existing ticket covers it (verified against the backlog 2026-07-05).
- **New bug ticket**: `GET /players/market/{player_id}/injuries` skips the PRIVATE-player visibility check that `player_market_detail` enforces — pre-existing, discovered during this spec's code verification; small, independent fix.
- **Ingestion note**: the `end`-date capture corrects silent data loss in the existing sidelined ingestion — worth a comment on whatever ticket originally shipped `PlayerInjury` (career/injury history) for traceability.

## Related documents

- [`fair-value-vs-asking-signal.md`](./fair-value-vs-asking-signal.md) — sibling signal; shared UI language, shared D6 player-exclusion stance
- [`../security-and-compliance/permissions-model.md`](../security-and-compliance/permissions-model.md) — medical-check confidentiality boundary D5 protects
- [`../architecture/data-model.md`](../architecture/data-model.md) — `PlayerInjury` entity (gains `end_date` on completion)
- [`README.md`](./README.md) — spec lifecycle

## Appendix: implementation gotchas (house-specific)

1. **UUID coercion with aiosqlite** — coerce `uuid.UUID(str(value))` before WHERE clauses in service code (test DB returns UUIDs as strings).
2. **Migration numbering race** — the sibling fair-value spec also allocates "next migration"; whichever is implemented second must re-check the head and chain off the real revision id, not the filename.
3. **No `index=True` + explicit `op.create_index` for the same column** in one migration (Postgres `DuplicateTable`). The `end_date` column needs no index.
4. **Timezone handling in the refresh** — the existing code normalizes naive `fetched_at` to UTC before comparing (`get_player_injuries`); keep that behaviour when extracting to the service.
5. **Money-style Decimal conversion is not needed here** — percentages/scores are plain floats rounded at the boundary; don't cargo-cult `Numeric` for a computed, unpersisted payload.
