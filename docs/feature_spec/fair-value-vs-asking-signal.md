---
title: "Feature Spec: Fair-Value-vs-Asking Signal (TRA-91 / TRA-92)"
last_updated: 2026-07-07
status: Implemented
owner: "TODO — assign a Product Owner"
---

# Feature Spec: Fair-Value-vs-Asking Signal

## Purpose

Full implementation specification for TransferX's independent player-valuation signal — an interpretable, performance-based "fair value" per player, shown against the asking/agreed price as a divergence signal (e.g. *"Asking £24.0m · Model £19.0m · +26% above model"*). This is Linear **TRA-91** (backend) and **TRA-92** (UI), scoped and de-risked on 2026-07-05 against the verified state of the codebase.

This document is written for an implementer (human or AI agent) with **no access to the conversation that produced it**. Everything needed to build and verify the feature is here or explicitly linked.

## How to use this document

1. Read [Decisions already made](#decisions-already-made) first — these were settled deliberately; do not relitigate them during implementation.
2. Implement backend per [The model](#the-model--exact-specification) and [Backend implementation](#backend-implementation), then UI per [UI specification](#ui-specification-tra-92).
3. Verify against [Success criteria](#success-criteria) — the three worked examples are exact test fixtures; the edge-case matrix and checklists are the review gate.
4. On completion, follow [Definition of done](#7-definition-of-done--tests-and-documentation) — including the documentation updates required by the [`documentation-standards`](../../.claude/skills/documentation-standards/SKILL.md) skill, and set this spec's `status` to `Implemented`.

Also read before writing code: the repo's `CLAUDE.md`, the [`engineering-standards`](../../.claude/skills/engineering-standards/SKILL.md) and [`product-principles`](../../.claude/skills/product-principles/SKILL.md) skills, and [Implementation gotchas](#implementation-gotchas-house-specific) below.

## Product context and value

TransferX is enterprise software for professional clubs, agents, and players — not a consumer app (see [`product-principles`](../../.claude/skills/product-principles/SKILL.md)). TRA-91 calls this feature "the flagship differentiator — TCA for transfers": rather than only displaying a third-party value, TransferX computes an **independent second opinion** and shows its divergence from the price on the table.

Value per stakeholder ([personas](../product/personas.md)):

| Stakeholder | Value |
|---|---|
| Buying club | An overpay check at the point of decision — listing page and deal room — before committing millions. |
| Selling club | A pricing sanity check on their own listings; the same signal, symmetrically. |
| Sporting Director | A defensible, documented number to carry into an internal debate ("the platform model says £19m; here's why"). |
| Agent | A negotiation anchor independent of either club's claim. |

**Known product tension, resolved deliberately:** a marketplace publishing "above model" against its own sellers' listings will not always please sellers. This is accepted — an honest market view is the product's stated differentiator, the signal is symmetric (sellers use it to price), and the tone rules below keep it a *model estimate*, never a verdict. Do not soften or hide the signal to avoid this tension.

## Scope

### In scope (v1)

- Backend valuation engine: performance score → fair value with confidence band, computed from data **already in the database** (see [Data inputs](#data-inputs-verified-available-2026-07-05)).
- Persistence with full input snapshot and model version (auditability + future model comparison).
- API: single + batch read endpoints, staff recompute, and a `fair_value_signal` block embedded in the sale detail response.
- Daily scheduled recompute (APScheduler, house pattern).
- UI: badge on player cards, full signal strip on player/sale detail, divergence in the deal room, breakdown popover.

### Explicitly out of scope (v1)

| Deferred item | Why | Where it's tracked |
|---|---|---|
| Divergence vs licensed ETV valuation | TRA-91's original AC mentions it, but the ETV adapter is verified inactive as of 2026-07-05: no `ETV_API_KEY` configured anywhere, and no `Player.etv_player_id` values populated (entity mapping is TRA-103, unbuilt). Comparing against a feed that returns nothing is not shippable. | Note on TRA-91 when closing (see [Linear reconciliation](#linear-reconciliation-suggested-not-executed)) |
| Expected goals (xG) inputs | API-Football (the live stats vendor) does not provide xG in any endpoint — verified 2026-07-05. An xG-capable vendor is planned **months later, after demos**. The architecture below reserves a slot for it (D3). | Future ticket, not yet created |
| Multi-currency | All money GBP, matching the platform-wide `formatCurrency` convention. | TRA-83/84 |
| Admin tuning UI for model constants | Constants live in one code module; tuning is a code change in v1. | Future ticket if needed |
| Valuation trend charts | The append-only history table accrues the data for this from day one; no UI yet. | Future ticket |
| Any ML/trained model | v1 is a deterministic formula per TRA-91's own "start simple and interpretable". | — |

## Decisions already made

Settled 2026-07-05 with the product owner. **Do not reverse these during implementation** — if one proves impossible, stop and surface it rather than silently choosing differently (per [`engineering-standards`](../../.claude/skills/engineering-standards/SKILL.md) §4).

- **D1 — v1 compares fair value vs asking/agreed price only, not vs ETV.** Reason: ETV pipeline is a verified no-op today (no key, no ID mapping). The asking price is internal (`Sale.asking_price`) and always available for fixed-price listings.
- **D2 — Build on season-aggregate box-score stats already flowing into `PlayerStats`.** No new vendor, no fixture-level ingestion. API-Football has no xG; fixture-level API-Football stats would be effort spent on a source that still lacks xG and is not the long-term plan.
- **D3 — Decouple feature extraction from scoring, and version every persisted valuation.** A `FeatureProvider` protocol (mirroring `backend/app/enrichment/protocols.py`) supplies a `FeatureSet`; the scoring engine consumes only the `FeatureSet`. When a real xG vendor lands (~months later), a new provider slots in and `model_version` bumps (`boxscore-v1` → `xg-v2`), so valuations from different model eras are never silently mixed.
- **D4 — League strength is a static, hand-maintained tier table** in a constants module. API-Football has no league-strength field; a tier table is the legitimate "simple and interpretable" start. Neutral conservative default for unknown leagues.
- **D5 — The UI presents an estimate, never a verdict.** Confidence band always shown; tone rules below are mandatory (e.g. "Above model", never "overpriced").
- **D6 — Player accounts never see the signal.** Server-enforced by `user_type`. Rationale: the signal is club/agent decision-support; showing a player "your transfer is 26% above model" mid-deal destabilises negotiations. This mirrors the existing house pattern of hiding commission fields from the player in `_build_deal_response`.
- **D7 — Auction listings never show divergence vs any seller-side number.** `reserve_price` and best bid are seller-only (TRA-139 closed that leak; see [permissions-model](../security-and-compliance/permissions-model.md)). A divergence against a hidden reserve would leak it. Auctions show fair value + range only.

## Data inputs (verified available 2026-07-05)

All verified against the live codebase, not assumed from tickets.

| Input | Source (module / table / column) | Notes |
|---|---|---|
| Season box-score stats | `app/stats/models.py::PlayerStats` — `goals`, `assists`, `appearances`, `minutes`, `avg_rating`, `shots_total`, `shots_on_target`, `key_passes`, `pass_accuracy`, `passes_total`, `tackles_total`, `interceptions`, `blocks`, `duels_total`, `duels_won`, `dribbles_attempts`, `dribbles_success`, `saves`, `goals_conceded`, `league_id`, `season` | Fed by API-Football `/players` season aggregates (`vendor = "api_sports_v3"`). Nulls are common on smaller leagues — see null rules. |
| Age | `app/players/models.py::Player.age`, fallback `Player.birth_date` | Either may be null. |
| Position | `Player.position` — enum `GK / DEF / MID / FWD` | Nullable; no valuation without it. |
| Asking price | `app/sales/models.py::Sale.asking_price` (`Numeric(15,2)`, nullable), `Sale.sale_type` (`AUCTION / FIXED_PRICE / OPEN_TO_OFFERS`) | Reference price for listings. |
| Agreed fee | `Deal` terms (deal room) | Reference price in deal context. |
| League tier | **Does not exist** — created by this feature as a constants table keyed by API-Football league id (`WorldLeague.league_id` strings) | See D4. |

**Not available, and must not be silently invented:** xG (no vendor field), per-match stats (never ingested), reliable wage data (`Capology` adapter inactive), ETV valuation (adapter inactive). If a formula input below is missing for a player, follow the null rules — never fabricate.

## The model — exact specification

Deterministic, pure-function formula. Same inputs ⇒ same outputs, always. House precedent for the idiom (clamped weighted blend, `Decimal(str(round(...)))` at the boundary) is `backend/app/vendor/form.py::compute_form_score` — match its style.

### Stage 0 — Eligibility

Compute a valuation for a player only if **all** hold:

1. `Player.position` is not null.
2. At least one `PlayerStats` row exists with `vendor = "api_sports_v3"`.
3. The selected stats row (Stage 1) has `minutes ≥ 450` (≈5 full matches).

Ineligible players get **no valuation row**: single GET returns 404, batch omits them, sale embed is `null`. Never render a made-up number.

### Stage 1 — Stats row selection

A player can have multiple `PlayerStats` rows (per league/season). Select exactly one:

1. Filter to `vendor = "api_sports_v3"` rows whose `season` parses as an integer (skip null/non-numeric).
2. Keep rows of the **latest season** (max integer value).
3. Of those, pick the row with the **greatest `minutes`** (ties: greater `appearances`, then lowest `league_id` string for determinism).

That row supplies all stats and the `league_id` for tier lookup.

### Stage 2 — Feature extraction (per-90 and rates)

With `n90 = minutes / 90`:

- `metric_per90 = metric / n90` for count stats.
- `duels_won_rate = duels_won / duels_total` (0 if `duels_total` is 0 or null).
- `defensive_actions_per90 = (tackles_total + interceptions + blocks) / n90` (null components count as 0).
- **Null rules:** any null count stat contributes 0 to its per-90. Null `avg_rating` → rating norm fixed at **0.5** and confidence capped at MEDIUM. Null age → age factor **0.85** and confidence capped at MEDIUM.

### Stage 3 — Normalisation benchmarks and position weights

Each feature normalises to [0,1] via `clamp(value / benchmark, 0, 1)` unless a range form is given. Rating norm (all positions): `clamp((avg_rating − 6.0) / 2.0, 0, 1)`.

**FWD** (weights sum 100):

| Feature | Benchmark (=1.0) | Weight |
|---|---|---|
| goals_per90 | 0.80 | 35 |
| assists_per90 | 0.40 | 15 |
| shots_on_target_per90 | 1.60 | 10 |
| key_passes_per90 | 1.80 | 10 |
| dribbles_success_per90 | 1.80 | 10 |
| rating norm | — | 20 |

**MID** (sum 100):

| Feature | Benchmark / form | Weight |
|---|---|---|
| goals_per90 | 0.35 | 15 |
| assists_per90 | 0.35 | 20 |
| key_passes_per90 | 2.20 | 20 |
| pass_accuracy | `clamp((acc − 70) / 20, 0, 1)` | 10 |
| duels_won_rate | `clamp((rate − 0.40) / 0.25, 0, 1)` | 10 |
| defensive_actions_per90 | 4.50 | 10 |
| rating norm | — | 15 |

**DEF** (sum 100):

| Feature | Benchmark / form | Weight |
|---|---|---|
| defensive_actions_per90 | 6.00 | 30 |
| duels_won_rate | `clamp((rate − 0.45) / 0.25, 0, 1)` | 20 |
| pass_accuracy | `clamp((acc − 70) / 20, 0, 1)` | 15 |
| goals_plus_assists_per90 | 0.15 | 10 |
| rating norm | — | 25 |

**GK** (sum 100):

| Feature | Benchmark / form | Weight |
|---|---|---|
| saves_per90 | 3.00 | 30 |
| goals_conceded_per90 (inverted) | `clamp((1.6 − gc90) / 1.2, 0, 1)` | 30 |
| pass_accuracy | `clamp((acc − 60) / 25, 0, 1)` | 15 |
| rating norm | — | 25 |

`performance_score = Σ (weight_i × norm_i)` — range [0,100]. Store rounded to 2 dp.

### Stage 4 — Fair value

```
fair_value_raw = base_anchor[position] × tier_multiplier[league] × (performance_score / 50) ^ 2.2 × age_factor
```

with the value-curve term floored at **0.05**.

**Base anchors** (GBP; the value of a hypothetical score-50 player in a Tier-1 league):

| Position | Anchor |
|---|---|
| GK | £8,000,000 |
| DEF | £12,000,000 |
| MID | £15,000,000 |
| FWD | £18,000,000 |

**League tiers** (constants module; keyed by API-Football `league_id`):

| Tier | Multiplier | Leagues |
|---|---|---|
| 1 | 1.00 | Premier League (39), La Liga (140), Serie A (135), Bundesliga (78), Ligue 1 (61) — ids verified against `backfill_2025.py` |
| 2 | 0.40 | Championship, Eredivisie, Primeira Liga, Belgian Pro League, Süper Lig, Scottish Premiership, Brazil Série A, MLS |
| 3 / unknown | 0.15 | Everything else, and any league id not in the table |

> **TODO (implementation-time):** confirm the Tier-2 vendor league ids against the `world_leagues` table in the dev DB before seeding the constant — do not guess ids. Tier-1 ids above are verified.

**Age factor** (from `Player.age`, else floor-years from `birth_date`; both null → 0.85 + confidence cap MEDIUM):

| Age | Factor | | Age | Factor |
|---|---|---|---|---|
| ≤18 | 0.80 | | 29 | 0.85 |
| 19–20 | 0.90 | | 30 | 0.75 |
| 21–23 | 0.98 | | 31 | 0.65 |
| 24–27 | 1.00 | | 32 | 0.55 |
| 28 | 0.92 | | 33 | 0.45 |
| | | | 34 | 0.38 |
| | | | ≥35 | 0.30 |

**Rounding:** compute in float, then `fair_value = round to nearest £100,000`, converted `Decimal(str(...))` at the boundary (house pattern). The confidence band applies to the **unrounded** value, each bound then rounded to £100k.

### Stage 5 — Confidence

| Level | Conditions (all must hold) | Band |
|---|---|---|
| HIGH | minutes ≥ 1800 **and** `avg_rating` present **and** stats `updated_at` within 60 days | ±15% |
| MEDIUM | minutes ≥ 900 **and** stats `updated_at` within 120 days | ±30% |
| LOW | minutes ≥ 450 (eligibility floor) | ±45% |

Caps from null rules (rating/age null → max MEDIUM) apply after the table. `fair_value_low = unrounded × (1 − band)`, `fair_value_high = unrounded × (1 + band)`, each rounded to £100k.

### Stage 6 — Divergence (computed at read time, never stored)

Against a reference price (listing asking price, or agreed fee in a deal):

```
divergence_pct = (reference_price − fair_value) / fair_value × 100     # fair_value = stored rounded value
```

Rounded to 1 dp. Band (applied to the rounded pct):

| Band enum | Range | Display copy |
|---|---|---|
| `WELL_BELOW` | pct ≤ −25 | "Well below model" |
| `BELOW` | −25 < pct ≤ −10 | "Below model" |
| `IN_LINE` | −10 < pct < +10 | "In line with model" |
| `ABOVE` | +10 ≤ pct < +30 | "Above model" |
| `WELL_ABOVE` | pct ≥ +30 | "Well above model" |

Divergence is computed against the stored rounded `fair_value` so displayed numbers always reconcile for the user.

### Worked examples — exact test fixtures

Implementations must reproduce these within tolerance: **performance_score ± 0.05, money values ± £100,000, divergence ± 0.2 pct-points.** Intermediates shown so a failing test can be bisected.

#### Example A — elite Tier-1 forward

Inputs: FWD, age 25, minutes 2700 (n90 = 30), goals 24, assists 9, shots_on_target 54, key_passes 45, dribbles_success 60, avg_rating 7.6, league_id "39" (Tier 1), stats fresh (< 60 days). Listed at asking £80,000,000.

| Feature | Per-90 / value | Norm | Weight | Contribution |
|---|---|---|---|---|
| goals | 0.800 | 1.000 | 35 | 35.000 |
| assists | 0.300 | 0.750 | 15 | 11.250 |
| shots on target | 1.800 | 1.000 (clamped) | 10 | 10.000 |
| key passes | 1.500 | 0.833 | 10 | 8.333 |
| dribbles success | 2.000 | 1.000 (clamped) | 10 | 10.000 |
| rating 7.6 | — | 0.800 | 20 | 16.000 |

- `performance_score` = **90.58**
- value curve = (90.583/50)^2.2 = 1.81167^2.2 ≈ **3.6965**
- `fair_value_raw` = 18,000,000 × 1.00 × 3.6965 × 1.00 (age 25) ≈ £66,537,000 → **fair_value £66,500,000**
- confidence **HIGH** (±15%): low = 66,537,000 × 0.85 → **£56,600,000**; high × 1.15 → **£76,500,000**
- divergence vs £80m = (80.0 − 66.5)/66.5 = **+20.3%** → band **`ABOVE`** → "Above model"

#### Example B — young rotation midfielder, no listing

Inputs: MID, age 20, minutes 1080 (n90 = 12), goals 2, assists 3, key_passes 20, pass_accuracy 84, duels_total 120, duels_won 66, tackles 18, interceptions 12, blocks 2, avg_rating 7.0, league_id "39", stats fresh. Not listed for sale.

| Feature | Per-90 / value | Norm | Weight | Contribution |
|---|---|---|---|---|
| goals | 0.167 | 0.476 | 15 | 7.143 |
| assists | 0.250 | 0.714 | 20 | 14.286 |
| key passes | 1.667 | 0.758 | 20 | 15.152 |
| pass accuracy 84 | — | 0.700 | 10 | 7.000 |
| duels won 0.550 | — | 0.600 | 10 | 6.000 |
| defensive actions | 2.667 | 0.593 | 10 | 5.926 |
| rating 7.0 | — | 0.500 | 15 | 7.500 |

- `performance_score` = **63.01**
- value curve = (63.006/50)^2.2 ≈ **1.6631**
- `fair_value_raw` = 15,000,000 × 1.00 × 1.6631 × 0.90 (age 20) ≈ £22,451,000 → **fair_value £22,500,000**
- confidence **MEDIUM** (1080 min; ±30%): low → **£15,700,000**; high → **£29,200,000**
- no reference price → `divergence: null`; UI shows fair value + range only

#### Example C — veteran Tier-2 defender, listed below model

Inputs: DEF, age 33, minutes 2430 (n90 = 27), tackles 62, interceptions 40, blocks 12, duels_total 300, duels_won 174, pass_accuracy 78, goals+assists 3, avg_rating 7.1, league in Tier 2, stats fresh. Listed at asking £2,500,000.

| Feature | Per-90 / value | Norm | Weight | Contribution |
|---|---|---|---|---|
| defensive actions | 4.222 | 0.704 | 30 | 21.111 |
| duels won 0.580 | — | 0.520 | 20 | 10.400 |
| pass accuracy 78 | — | 0.400 | 15 | 6.000 |
| goals+assists | 0.111 | 0.741 | 10 | 7.407 |
| rating 7.1 | — | 0.550 | 25 | 13.750 |

- `performance_score` = **58.67**
- value curve = (58.668/50)^2.2 ≈ **1.4215**
- `fair_value_raw` = 12,000,000 × 0.40 (Tier 2) × 1.4215 × 0.45 (age 33) ≈ £3,071,000 → **fair_value £3,100,000**
- confidence **HIGH** (±15%): low → **£2,600,000**; high → **£3,500,000**
- divergence vs £2.5m = (2.5 − 3.1)/3.1 = **−19.4%** → band **`BELOW`** → "Below model"

## Backend implementation

### Module layout

New module `backend/app/valuation/` following the house `models.py / schemas.py / service.py / router.py` layering ([backend-architecture](../architecture/backend-architecture.md)), plus three files specific to this feature's decoupling requirement (D3):

| File | Contract |
|---|---|
| `models.py` | `PlayerValuation` table + `ValuationConfidence` enum (`HIGH/MEDIUM/LOW`). |
| `constants.py` | **Every tunable in one place**: base anchors, tier table, age curve, benchmarks, weights, curve exponent, confidence thresholds/bands, divergence bands, `MODEL_VERSION = "boxscore-v1"`. Nothing numeric hard-coded elsewhere. |
| `features.py` | `FeatureSet` dataclass + `FeatureProvider` protocol (mirror `enrichment/protocols.py` style) + `BoxScoreFeatureProvider` (implements Stages 1–2 from `PlayerStats`/`Player`). |
| `engine.py` | **Pure functions, no DB**: `compute_performance_score(features) -> float`, `compute_fair_value(features, score) -> ValuationOutcome` (value, low, high, confidence, factors), `compute_divergence(fair_value, reference_price) -> Divergence`. Unit-testable without fixtures. |
| `schemas.py` | Response schemas (below). Mirror the existing money-field serialization used by `SaleResponse.asking_price` — do not invent a new money encoding. |
| `service.py` | Orchestration: eligibility → provider → engine → persist; `get_latest_valuation(db, player_id)`; `get_latest_valuations(db, player_ids)` (batch, no N+1 — one query using the `(player_id, computed_at)` index); `compute_all_valuations(db)` for the job. |
| `router.py` | Endpoints below, mounted in `app/main.py` under prefix `/valuation`. |

### Data model and migration

Table `player_valuations` — **append-only** (history is the audit trail and future trend-chart data; "latest" = max `computed_at` per player):

| Column | Type | Notes |
|---|---|---|
| `id` | UUID pk | default `uuid4` |
| `player_id` | UUID FK → `players.id`, `ondelete="CASCADE"` | |
| `fair_value` / `fair_value_low` / `fair_value_high` | `Numeric(15, 2)` | GBP |
| `currency` | `String(10)` | always `"GBP"` in v1 |
| `performance_score` | `Numeric(5, 2)` | |
| `confidence` | `SAEnum(ValuationConfidence)` | |
| `model_version` | `String(50)` | `"boxscore-v1"` |
| `league_tier` | `Integer` | 1/2/3 as resolved |
| `age_factor` | `Numeric(4, 2)` | |
| `inputs_json` | `JSON().with_variant(JSONB, "postgresql")` | Full `FeatureSet` + per-feature norms/contributions snapshot — the auditability answer: any historical number is fully explainable. **Must not be bare `JSONB`** (breaks the SQLite test suite — see gotchas). |
| `computed_at` | `DateTime` | default now |

Index: `(player_id, computed_at)` — create **explicitly** with `op.create_index`, no `index=True` on those columns (gotcha: mixing both duplicates the index).

Migration: next number after the current head (`0047_agent_negotiation_commission_only` as of 2026-07-05 — re-check `backend/migrations/versions/` and use the 0047 file's actual revision id as `down_revision`, not its filename).

### API contract

All endpoints require authentication. **`user_type == PLAYER` receives 403 on all of them** (D6). Player visibility must mirror the existing rule in `players/router.py::player_market_detail` (PRIVATE → 404 unless creator; the valuation endpoint must not be a side-channel to a hidden player's quality).

**`GET /valuation/players/{player_id}?reference_price=<int|omitted>`** → 200:

```json
{
  "player_id": "5f0c…",
  "fair_value": 66500000.0,
  "fair_value_low": 56600000.0,
  "fair_value_high": 76500000.0,
  "currency": "GBP",
  "performance_score": 90.58,
  "confidence": "HIGH",
  "model_version": "boxscore-v1",
  "league_tier": 1,
  "age_factor": 1.0,
  "as_of": "2026-07-05T03:00:00Z",
  "breakdown": [
    {"label": "Goals per 90", "value": "0.80", "norm": 1.0, "weight": 35, "contribution": 35.0},
    {"label": "Average rating", "value": "7.6", "norm": 0.8, "weight": 20, "contribution": 16.0}
  ],
  "divergence": {
    "reference_price": 80000000.0,
    "pct": 20.3,
    "band": "ABOVE"
  }
}
```

- `divergence` is `null` when `reference_price` is omitted.
- 404 when the player has no valuation (ineligible) or is not visible to the caller.
- `breakdown` lists every weighted feature, ordered by contribution descending — this drives the UI popover.

**`GET /valuation/players?ids=<uuid,uuid,…>`** (cap 50, else 422) → 200 with `{"valuations": {"<player_id>": {…same shape…}}}`. Ineligible/invisible players are silently omitted — the market grid must not error because one card lacks data.

**Amended 2026-08-24 — the batch does carry divergence.** As originally specified it never did, because a batch cannot take a `reference_price` query arg. But `PlayerMarketPage` was built to read `divergence` from it in three places, so its value sort, its under-fair-value counter and the whole "asking vs fair value" cell in `PlayerListRow` were permanently empty. The server now resolves a reference price per player instead, under exactly the per-sale-type rule the detail embed below applies: an **open non-auction listing's** `asking_price`, else the legacy `Player.market_value`, else none (and so no divergence). D6 and D7 are untouched — auctions are excluded by the same rule, and a batch must never surface what the detail endpoint withholds. One extra query per batch, never one per player.

**`POST /valuation/players/{player_id}/recompute`** — staff only (`get_current_superuser`), synchronously recomputes and returns the fresh valuation. Log at INFO; no deal-audit event (the audit log is deal-scoped; `inputs_json` + `computed_at` + `model_version` already give the required trail — this satisfies the engineering-standards auditability question deliberately, not by omission).

**Sale detail embed** — `GET /sales/{id}` response gains `fair_value_signal: {…} | null`:

- `FIXED_PRICE` or `OPEN_TO_OFFERS` **with** `asking_price` set: full signal **with** divergence vs `asking_price`. *(`OPEN_TO_OFFERS` amended 2026-08-24 — originally "without divergence". Reversed with the product owner: that exclusion was semantic, not confidentiality, and an `OPEN_TO_OFFERS` asking price is already published on the listing exactly as a fixed price is. D7's exclusion is narrower than it was being read — it names auctions, whose seller-side numbers are the hidden ones.)*
- `FIXED_PRICE` or `OPEN_TO_OFFERS` **without** `asking_price` set: full signal **with** divergence vs the legacy `Player.market_value`, same fallback as the batch above. *(Added 2026-08-24 — `asking_price` is optional at creation for every sale type; nothing before this required a club to set one outside `AUCTION`'s deadline requirement, so a listing with none set was a reachable gap, not a hypothetical: this same player's row in the market list could already show a divergence via `market_value` while his own sale page showed none.)* No divergence at all when `market_value` is also unset.
- `AUCTION`: signal **without** divergence, regardless of `market_value` (D7 — never against `reserve_price` or any bid figure). The only excluded listing type.
- `null` when: player ineligible, **or the viewer is a PLAYER account** (field-scope it exactly like commission fields are scoped out of `_build_deal_response`).

**Deal room** — no backend change: the frontend calls the single GET with `reference_price = <agreed fee>` for club/agent/staff viewers only.

### Scheduled job

Daily APScheduler job registered in `app/main.py` (house pattern; run after the enrichment sync job). Calls `compute_all_valuations`; logs `updated / skipped_ineligible / errors` counts like the enrichment job does. Per-player failures are caught and logged, never abort the batch.

### Backend files-to-touch checklist

- [ ] `backend/app/valuation/` — `__init__.py`, `models.py`, `constants.py`, `features.py`, `engine.py`, `schemas.py`, `service.py`, `router.py` (new)
- [ ] `backend/migrations/versions/0048_player_valuations.py` (new; verify numbering/down_revision)
- [ ] `backend/app/main.py` — mount router, register daily job
- [ ] `backend/app/sales/router.py` + `sales/schemas.py` — `fair_value_signal` embed
- [ ] `backend/tests/test_valuation.py` (new) + sale-embed cases in `backend/tests/test_sales.py`

## UI specification (TRA-92)

House design system: dark theme (`bg-slate-950` body, `bg-slate-900` cards), emerald accent, money via the shared `formatCurrency` (£). Server state via TanStack Query. New enums/types go in `frontend/src/types/enums.ts` and `types/api.ts` (`FairValueSignal`, `ValuationBand`, `ValuationConfidence`).

### Components (new)

**`FairValueBadge`** — `frontend/src/components/players/FairValueBadge.tsx`

- Props: `{ signal: FairValueSignal; referenceLabel?: string; compact?: boolean }`.
- `compact` (cards): one pill — `Model £66.5m · +20%` when divergence exists, else `Model £66.5m`.
- Full (detail pages): one strip — `Asking £80.0m · Model £66.5m (range £56.6m–£76.5m) · +20% above model`, followed by the confidence tag and an info trigger opening the breakdown popover.
- Band colors: `WELL_BELOW` emerald-500 · `BELOW` emerald-400 · `IN_LINE` slate-400 · `ABOVE` amber-400 · `WELL_ABOVE` rose-400. LOW confidence always renders muted with a "Low confidence" suffix regardless of band.
- Renders `null` when `signal` is absent — never a placeholder value.

**`ValuationBreakdownPopover`** — `frontend/src/components/players/ValuationBreakdownPopover.tsx`

- Content, in order: top 5 `breakdown` rows (label, per-90 value, contribution), age factor line ("Age 25 — peak years"), league tier line, confidence line with reason ("2,700 minutes this season"), footer: `Model boxscore-v1 · as of 5 Jul 2026 · Model estimate — not an official valuation.`
- The footer disclaimer is mandatory (D5).

### Surface-by-surface

| Surface | Change |
|---|---|
| `PlayerCard` (market grid) | Compact badge row when a signal exists for that player. Grid pages fetch via the **batch endpoint** (one call per page of cards, not per card). |
| `PlayerMarketDetailPage` | Full strip near the valuation/market-value area; fair value + range only (no reference price on a profile). |
| `SaleDetailPage` | Full strip from the embedded `fair_value_signal`; divergence appears for `FIXED_PRICE` and `OPEN_TO_OFFERS`, never for `AUCTION` (D7). |
| `DealDetailPage` (deal room) | One line in/near the Terms card: full strip with `reference_price = agreed fee`, `referenceLabel="Agreed fee"`. Rendered only for club/agent/staff identities (server 403s player accounts anyway — the UI simply must not fire the call for a player identity, using the existing `useIdentity` hook). |

### States

| State | Behaviour |
|---|---|
| No signal (ineligible player) | Cards: nothing. Detail pages: muted single line — `No model valuation — insufficient recent data.` |
| Loading | Existing `Skeleton` component, badge-sized; never layout-shift a whole card. |
| Error (endpoint failure) | Render nothing (cards) / the muted line (detail). The signal is an enhancement — it must never block or error a page. |
| Stale (`as_of` > 60 days) | Append `as of <date>` in amber to the strip. |
| LOW confidence | Muted styling + "Low confidence" tag, always. |
| Player-account viewer | Nothing rendered anywhere; no valuation request issued. |

### Copy rules (mandatory, D5)

Only these divergence phrases: "Well below model" / "Below model" / "In line with model" / "Above model" / "Well above model". Never: "overpriced", "bargain", "rip-off", "steal", or any imperative ("don't pay this"). The word is always **model** — never "true value" or "real value".

### Frontend files-to-touch checklist

- [ ] `src/types/api.ts`, `src/types/enums.ts` — new types/enums
- [ ] `src/components/players/FairValueBadge.tsx` + `FairValueBadge.test.tsx` (new)
- [ ] `src/components/players/ValuationBreakdownPopover.tsx` (new)
- [ ] `src/components/players/PlayerCard.tsx` — compact badge
- [ ] `src/pages/market/PlayerMarketDetailPage.tsx`, `src/pages/market/SaleDetailPage.tsx`, `src/pages/deals/DealDetailPage.tsx` — integration
- [ ] Market grid page — batch fetch wiring

## Success criteria

The review gate. An implementation is done when every item below passes.

### 1. Backend functional acceptance

- [ ] Eligible player: GET returns the full shape, with `breakdown` ordered by contribution descending.
- [ ] `reference_price` present ⇒ `divergence` computed against the **stored rounded** `fair_value`, with correct band per the boundary table.
- [ ] Ineligible player (no stats / minutes < 450 / no position): no row persisted; GET 404; batch omits; sale embed `null`.
- [ ] Batch endpoint: ≤ 50 ids, one DB round-trip for latest-per-player (no N+1), silently omits missing.
- [ ] Recompute endpoint: superuser only (club/agent/player → 403), persists a **new** row (append-only, old rows untouched).
- [ ] Daily job registered and idempotent; a per-player failure doesn't abort the batch.
- [ ] `inputs_json` on every row reproduces the computation: feeding it back through the engine yields the stored outputs.

### 2. Reference fixtures

- [ ] Unit tests encode Examples A, B, C **exactly** (inputs → expected score / fair value / band / confidence, within stated tolerances). These are the canonical regression tests for any future constant tuning.

### 3. Edge-case matrix

| Input condition | Required behaviour |
|---|---|
| `minutes` 449 | No valuation (floor is ≥ 450) |
| `minutes` 450 | Valuation with LOW confidence, ±45% band |
| `avg_rating` null | Rating norm 0.5; confidence ≤ MEDIUM |
| `age` and `birth_date` both null | Age factor 0.85; confidence ≤ MEDIUM |
| `duels_total` 0 or null | Duels norm 0, no division error |
| `position` null | No valuation |
| Unknown `league_id` | Tier 3 multiplier 0.15 — never an error |
| Multiple stats rows | Selection follows Stage 1 exactly (latest season, then max minutes) |
| PRIVATE player, non-creator caller | 404 (mirrors `player_market_detail`) |
| PLAYER-type account, any endpoint | 403 |
| AUCTION sale embed | Signal present, `divergence` null — **assert nothing derived from `reserve_price` appears** |
| Score 100 (all norms 1.0) | Curve = 2^2.2 ≈ 4.59× anchor; no overflow/clamp error |

### 4. Calibration sanity checklist (run against seeded dev data, eyeball before demo)

- [ ] No player anywhere valued above £150m or below £100k (floored curve).
- [ ] Median Tier-1 regular (score ~50, age 24–27) lands £8m–£18m by position — by construction.
- [ ] Same stats, Tier 2 vs Tier 1 ⇒ exactly 0.40×.
- [ ] A 33-year-old is valued visibly below an otherwise-identical 25-year-old (0.45 vs 1.00).
- [ ] Spot-check ~5 well-known seeded players; if a number is absurd, tune `constants.py` — **fixtures in §2 are the regression net for any tuning** (they must be updated in the same commit as any constant change, deliberately).

### 5. UI acceptance

- [ ] Market grid: compact badges on eligible players; one batch call per page; zero badges ⇒ zero layout artifacts.
- [ ] Sale detail (FIXED_PRICE, asking £80m, fixture-A player): exact strip `Asking £80.0m · Model £66.5m (range £56.6m–£76.5m) · +20% above model` with amber `ABOVE` styling.
- [ ] Auction sale detail: fair value + range shown, **no divergence figure anywhere**.
- [ ] Deal room: strip vs agreed fee for club/agent/staff; nothing for a player participant.
- [ ] Breakdown popover shows top-5 drivers + factors + confidence reason + mandatory disclaimer footer.
- [ ] All states in the states table behave as specified (loading, error, stale, LOW, ineligible).
- [ ] `FairValueBadge.test.tsx` covers: each band's label+color, LOW muting, compact vs full, null ⇒ renders nothing.

### 6. Non-functional

- [ ] **Determinism:** engine unit test — same `FeatureSet` twice ⇒ identical outputs.
- [ ] **Purity:** `engine.py` imports no DB/session modules.
- [ ] **Performance:** batch valuation for 50 players ⇒ 1 query; sale-detail embed adds ≤ 1 query.
- [ ] **Permissions tests exist** for: unauthenticated 401, player-account 403, PRIVATE-player 404, staff-only recompute.
- [ ] TypeScript compiles clean; full backend suite green (274 baseline + new).

### 7. Definition of done — tests and documentation

Per [`documentation-standards`](../../.claude/skills/documentation-standards/SKILL.md), in the same session as implementation:

- [ ] `docs/CHANGELOG.md` — `Added` entry.
- [ ] `docs/IMPLEMENTATION_STATUS.md` — row for this feature, verified state.
- [ ] `docs/engineering/api-reference.md` — `/valuation` in the prefix map.
- [ ] `docs/architecture/data-model.md` — `PlayerValuation` row.
- [ ] `docs/architecture/backend-architecture.md` — `valuation` module row.
- [ ] `docs/business/glossary.md` — "Fair value (model)" and "Divergence" entries.
- [ ] This spec — `status: Implemented`, plus a short "Deviations from spec" note (even if "none").
- [ ] Suggest (do **not** execute) Linear updates per below.

### 8. Demo script (end-to-end, the final gate)

1. Seed/identify a FIXED_PRICE listing whose player has ≥ 1800 minutes of Tier-1 stats.
2. Log in as a **buying club** → market grid shows the compact badge on that card.
3. Open the sale → full strip with divergence and correct band color; open breakdown popover → drivers + disclaimer.
4. Open an in-progress deal as the buying club → strip vs agreed fee in the Terms area.
5. Log in as the **player** on that deal → no signal anywhere in the deal room; direct GET to the valuation endpoint → 403.
6. Open an AUCTION listing as a rival club → fair value + range, no divergence, and nothing derivable about the reserve.

## Deviations from spec (implemented 2026-07-07)

Implemented as specified, with these deliberate deviations:

1. **Tier-2 league ids could not be confirmed against the dev DB** — no ingestion path has ever synced a Tier-2 league (only the top-5 plus UCL/EL, ids 2/3, are synced — verified in `backfill_2025.py` and `scripts/sync_leagues.py`), so `world_leagues` has nothing to confirm against. Seeded with API-Football's canonical public ids instead (Eredivisie 88 / Primeira Liga 94 web-confirmed; the rest from public documentation), flagged in `constants.py` for re-verification when a Tier-2 league is first synced. A wrong id degrades conservatively to Tier 3, never inflates. Related: UCL/EL stats rows (league ids 2/3) resolve to Tier 3 if ever selected by Stage 1 — acceptable-conservative, noted here for future tier-table tuning.
2. **`MIN_FAIR_VALUE_GBP = 100_000` floor added.** The curve floor alone doesn't guarantee the calibration invariant "no player below £100k" (worst case GK × Tier 3 × curve floor × age ≥35 ≈ £18k, which rounds to £0 and would break divergence). The constant enforces the invariant the spec asserts.
3. **The response schema gained additive `age` and `minutes` fields** (from the stored `inputs_json` snapshot) — the breakdown popover's required copy ("Age 25 — peak years", "2,700 minutes this season") needs them and the spec's response example didn't carry them.
4. **The sale-detail embed is also `null` for unauthenticated viewers**, not only player accounts — the `/valuation` endpoints themselves require authentication, so giving the anonymised public listing page the signal for free would have been an inconsistent boundary.
5. **Live verification (2026-07-07, dev stack):** migration `0048` applied; `compute_all_valuations` ran over the full dev DB — 2,229 valuations / 5,519 ineligible / 0 errors in 7.7s across 7,748 players. §4 calibration holds on real data: values span £100k–£68.4m, top of market is Dembélé (£68.4m) / Mbappé (£61.4m) / Pedri (£44.6m) / Haaland (£44m). §8 demo driven via the API: FIXED_PRICE listing (Mbappé @ £75m) shows +22.1% `ABOVE`; an auction with a £40m reserve carries no divergence and leaks nothing reserve-derived; a player account bound to the listed player gets 403 on `/valuation` and a null embed on his own sale; anonymous viewers get a null embed. Note: no HIGH-confidence valuations exist in dev — the stats backfill is >60 days old, so the freshness rule caps everything at MEDIUM (visible as the amber "as of" flag in the UI); expected, not a bug. Demo fixtures left in the dev DB: users `val-demo-{seller,buyer,player}@transferx.dev` (password `DemoPass123`), Mbappé/Pedri contracted to "Valuation Demo FC", one OPEN FIXED_PRICE and one OPEN AUCTION listing.

## Future evolution

- **xG vendor (planned, ~months post-demo):** implement a new `FeatureProvider`; extend `FeatureSet` with xG fields; add xG-aware weights; bump `MODEL_VERSION` to `xg-v2`. Historical `boxscore-v1` rows remain distinguishable — never retro-edit them.
- **ETV divergence (deferred TRA-91 scope):** needs an `ETV_API_KEY` + entity mapping (TRA-103). When live, add a second divergence axis (`vs_etv`) to the response rather than replacing `vs_asking`.
- **Multi-currency:** TRA-83/84 will touch `currency` and display; schema already carries the field.

## Linear reconciliation (suggested, not executed)

Per the [`linear-workflow`](../../.claude/skills/linear-workflow/SKILL.md) skill, these are suggestions for whoever closes the tickets — this spec does not modify Linear:

- **TRA-91:** on completion, comment that the "vs licensed ETV" acceptance criterion is deliberately deferred (adapter inactive: no key, no TRA-103 mapping) and link this spec — deliberate narrowing, not a miss.
- **TRA-92:** on completion, note D6 (player accounts excluded) and D7 (no divergence on auctions) as deliberate scope decisions with rationale here.
- **TRA-103:** comment that ETV-divergence for this feature is blocked on it, so the dependency is discoverable.

## Related documents

- [`../product/roadmap.md`](../product/roadmap.md) — Differentiation & Demo Readiness phase
- [`../architecture/backend-architecture.md`](../architecture/backend-architecture.md) / [`../architecture/data-model.md`](../architecture/data-model.md) — where the new module/entity get recorded on completion
- [`../security-and-compliance/permissions-model.md`](../security-and-compliance/permissions-model.md) — the confidentiality boundaries D6/D7 protect
- [`../business/glossary.md`](../business/glossary.md) — canonical term definitions (gains two entries on completion)

## Appendix: implementation gotchas (house-specific)

Hard-won project knowledge; violating these has broken this repo before:

1. **`JSONB` breaks the test suite.** The pytest suite runs on in-memory SQLite; a bare `sqlalchemy.dialects.postgresql.JSONB` column makes every test in the suite uncollectable. Use `JSON().with_variant(JSONB, "postgresql")` — the exact pattern now in `app/audit/models.py`.
2. **UUID coercion with aiosqlite.** In service functions, coerce before WHERE clauses: `uuid.UUID(str(value))` — aiosqlite returns UUIDs as strings and SQLAlchemy's `Uuid` bind processor calls `.hex` on them.
3. **Don't mix `index=True` with explicit `op.create_index`** for the same column in one migration — Postgres raises `DuplicateTable`. This migration uses explicit `op.create_index` only.
4. **Standalone scripts must import all model modules** (relationship string resolution) — relevant only if a backfill/seed script is added for valuations.
5. **Money at the boundary:** compute in float, convert once via `Decimal(str(...))` — the pattern in `vendor/form.py`. Match the existing serialization of `SaleResponse.asking_price` for API output.
