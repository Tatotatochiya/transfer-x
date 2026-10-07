---
title: "Feature Spec: Valuation Model v2 (market-v2)"
last_updated: 2026-10-07
status: Implemented — pending product-owner sign-off and production backtest
owner: "TODO — assign a Product Owner"
---

# Feature Spec: Valuation Model v2 (`market-v2`)

## Purpose

Replaces the fair-value engine behind the [Fair-Value-vs-Asking Signal](./fair-value-vs-asking-signal.md) (`boxscore-v1`) with a model that prices what a transfer market actually pays for: multi-season evidence, position-specific ageing, youth potential, trajectory, recent form, contract length, availability, and the fees comparable profiles have really fetched. Everything else in that spec still stands: endpoints, permissions (D6), auction rules (D7), divergence bands, append-only history and the "estimate, never a verdict" tone (D5).

`market-v2` remains deterministic and fully explainable (no trained model). Every factor is persisted as a *driver*, so any number can be rebuilt by hand, and every stored row replays exactly from its own `inputs_json`.

## Why v1 needed replacing

| v1 behaviour | Effect |
|---|---|
| One season, one stats row (the biggest-minutes row of the latest season) | A 500-minute hot streak priced like a full season; history and mid-season moves ignored |
| Step age table with no potential: ≤18 → ×0.80, 24–27 → ×1.00 | An elite 18-year-old was worth *less* than the same output at 26, the opposite of the market |
| `(score/50)^2.2` curve | The box-score score compresses the top end (elite ≈ 72, average ≈ 48) while fees differ ~10× across that gap. v1 priced Example A (24 PL goals at 25) at £66.5m |
| Three league tiers | Ligue 1 priced the same as the Premier League |
| No contract, injury, form or market inputs | A player with 6 months left was valued the same as one with 5 years; data already in the DB went unused |

## The model

```
fair_value = anchor[position]
           × league_coefficient
           × curve(performance)        multi-season, shrunk for sample size
           × age_factor × potential    position-specific peak; youth premium
           × trajectory × form
           × contract × availability
           × market_rate               comparable transfers, leave-own-out
           (capped at a published release clause)
```

All tunables are in `backend/app/valuation/constants_v2.py`. The engine (`engine_v2.py`) is pure; DB access lives in `features_v2.py`.

| Stage | Input (all already in the DB) | Rule |
|---|---|---|
| A. Performance | `PlayerStats`, up to 3 seasons | v1's per-position feature tables score each season. Rows within a season are aggregated (counts summed, rates minutes-weighted), so a mid-season move or a European run counts in full. Seasons blend by minutes × recency (1.0 / 0.55 / 0.30), then shrink toward a prior of 40 with 600 minutes' weight |
| B. Intrinsic | League id | Per-league coefficient (PL 1.00, La Liga 0.80, Serie A/Bundesliga 0.75, Ligue 1 0.62, …, unknown 0.13). Score → value multiple is log-linear between knots (50 → ×1.0, 60 → ×2.3, 70 → ×4.8, 80 → ×7.8, 90 → ×10.5) |
| C. Age | `Player.birth_date` / `age` | No discount before peak end (GK 31, DEF 29, MID/FWD 28); then `exp(−0.08y − 0.015y²)`, floored at 0.18 |
| C. Potential | Age, score, minutes | `1 + 1.2 × youth × quality × evidence`: youth fades from 1 at ≤19 to 0 at peak start; quality needs a score above 35; evidence needs ~2,000 weighted minutes. An unproven teenager earns little of it |
| C. Trajectory | Latest vs previous season score | ±10% for a ±20-point swing (half for players over 23); needs 900+ minutes in both seasons |
| D. Form | `PlayerFixtureRating` (last 5 games, 20+ min) | Recency-weighted rating vs season average, ×0.08 per rating point, capped at ±8%. Deliberately small |
| E. Contract | Active TransferX `Contract.end_date`, else vendor `Player.contract_expiry` ([ADR 0001](../architecture/decisions/0001-vendor-data-never-overrides-transferx-contract.md) precedence) | Knots: 0y → 0.30, 0.5y → 0.50, 1y → 0.70, 2y → 0.88, 3y+ → 1.00. Unknown → neutral |
| F. Availability | `PlayerInjuryFixture` vs `TeamSeasonFixtures`, last 2 seasons | No discount at ≥90% available, up to −20% at ≤50%. Suspensions excluded using the [risk profile](./injury-availability-risk-profile.md)'s D4 terms. Any team-season count unknown → neutral (no guessing) |
| G. Market rate | Completed TransferX deals (agreed fee) + vendor-reported fees ("€ 42M"), last 3 years | Each comparable is restated as *fee in today's £ ÷ the model's intrinsic value at the time*, using the stats the buyer had (pre-transfer seasons). Similarity-weighted median of that ratio, shrunk toward 1 by the effective number of comps, bounded to ×0.65–1.60. Needs ≥3 similar comps. A player's own transfers never price him. TransferX deals outweigh reported fees (×1.5) and win when both describe the same move |
| H. Confidence | — | Levels use v1's rules on the latest season (shared code). Band widens +10 pts at ≤21 (potential is uncertain) and narrows 3 pts when the market rate applied |

The release clause cap applies last: no buyer pays more than a published clause.

### Confidentiality

Only contract fields already visible to rival clubs are read: end date and release clause (see `test_contract_confidentiality.py`). Wage, signing date, notes and the holding club's own `club_valuation` are never inputs; a test asserts the latter never appears in `inputs_json`.

### Auditability

`inputs_json` stores the full `FeatureSetV2` snapshot (every season's features, recent games, contract, availability), the driver waterfall, and the market-rate result. `compute_valuation_v2(features_from_snapshot(...), market=MarketRate(**...))` reproduces the stored row exactly. The whole comparables index is too large to store, so it is replayed from the stored market result.

## Calibration (archetypes, not a backtest)

`backend/scripts/valuation_archetypes.py` runs realistic full-season profiles through both models. The "market" column is a rough public consensus range: it shows direction and scale, and is **not** ground truth.

| Archetype | Market £m | v1 £m | v2 £m |
|---|---|---|---|
| Elite PL striker, 25, 4y contract | 90–130 | 50.3 | **103.3** |
| Wonderkid winger, 18, La Liga | 130–200 | 32.2 | **103.7** |
| Elite PL midfielder, 26 | 80–110 | 35.4 | **81.4** |
| Elite striker, 33, La Liga, 1y left | 12–25 | 18.3 | **18.1** |
| Solid PL centre-back, 28 | 30–45 | 21.8 | **41.4** |
| Average PL full-back, 30 | 6–14 | 9.1 | **9.3** |
| Championship striker, 24, 18 goals | 8–18 | 9.5 | **8.9** |
| Eredivisie attacking mid, 20 | 25–45 | 14.0 | **48.5** |
| Elite PL goalkeeper, 30 | 25–40 | 12.3 | **29.6** |
| Danish league striker, 22 | 3–9 | 4.4 | **6.2** |
| Elite winger, 29, 6 months left | 25–45 | 39.2 | **41.5** |
| Same winger, 29, 4 years left | 55–80 | 39.2 | **83.1** |
| PL midfielder, 26, 60% available | 20–35 | 29.4 | **38.0** |
| Teen breakout, 19, 600 PL minutes | 15–35 | 32.0 | **32.8** |

v2 lands in range for 10 of 14 (v1: 3), and the rest are within ~10% of the range, except the elite teenager. That superstar premium is out of reach for any box-score model without comparables; the market-rate stage is the mechanism that closes it once similar transfers are in the data.

**First backtest, on the dev database (2026-10-07).** The dev database has 83 reported fees, all from API-Football, mostly from 2024. Pre-transfer stats cover about 650 players a season for 2022–2024.

| | within ±25% | within ±50% | median bias |
|---|---|---|---|
| v1 | 8.4% | 16.9% | −64% |
| v2 intrinsic | 9.6% | 18.1% | −65% |
| v2 + market | 20.5% | 24.1% | −49% |

- v2 + market beats v1 on every overall measure. Both models still sit well below the fees paid, and most of all above £25m (−67%).
- v2's intrinsic value alone is no closer than v1's.
- After a dev recompute, the market rate sits at its ×1.60 ceiling for 1,276 of 2,425 players (53%), and the median factor is the ceiling itself. So for most players the bound, not the comparables, sets the final number. The intrinsic scale (`BASE_ANCHORS_V2`, `VALUE_CURVE_KNOTS`) runs low against real fees.

The production backtest below is what should set those constants.

> **TODO:** run `python -m scripts.valuation_backtest` against production. It replays every fee-bearing transfer in the window through v1, v2 intrinsic and v2 + market (leave-own-out) and reports median error, share within ±25% / ±50% and bias by position, age, fee band and source. Tune `VALUE_CURVE_KNOTS`, `BASE_ANCHORS_V2` and `LEAGUE_COEFFICIENTS` from that, not from the archetypes.

## Decisions for the product owner

These were judgement calls made during implementation. Each is a single constant to change.

1. **Premier League premium within the old Tier 1.** v1 treated the top five leagues identically; v2 prices La Liga at 0.80 of the PL and Ligue 1 at 0.62. This matches how fees behave, but it is a visible change for clubs in those leagues.
2. **Expiring contracts are discounted hard** (6 months left → ×0.50). This is honest about pre-contract leverage, and it will show "below model" less often on listings of expiring players.
3. **Free agents** (no contract anywhere) get a neutral contract factor: the model values the player, not a fee. Showing £0 would be accurate for a fee but useless as a signal.
4. **The market-rate stage uses vendor-reported fees** (`PlayerTransfer.fee_display`, from API-Football) alongside TransferX deals. These are reported figures, not verified ones, and are weighted below TransferX deals for that reason.
5. **Existing valuations are not rewritten.** v1 rows stay in the append-only history (D3); new rows carry `model_version = "market-v2"` from the next daily recompute. The UI shows the v2 build-up only for v2 rows.

## Deliberately not used

The holding club's `club_valuation` and wages (confidential); `Player.market_value` (the vendor value the signal exists to be independent of); xG (no vendor yet; the `FeatureProvider` seam from D3 is still the place for it).

## Related

- [Fair-Value-vs-Asking Signal](./fair-value-vs-asking-signal.md): the signal, endpoints and UI this model feeds
- [Injury-Availability Risk Profile](./injury-availability-risk-profile.md): D4 suspension terms shared
- [ADR 0002](../architecture/decisions/0002-contract-cliff-prefers-fair-value-over-legacy-market-value.md): fair value preferred over `market_value` wherever both exist
