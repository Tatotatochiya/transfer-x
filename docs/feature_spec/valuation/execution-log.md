---
title: "Valuation: execution log for market-v3 and staff-entered fees"
last_updated: 2026-11-13
status: Reviewed 2026-11-13; §11 is current and supersedes §1–§10 where they differ
owner: "TODO — assign a Product Owner"
---

# Valuation Execution Log — `market-v3` and staff-entered fees

- **Plan:** [`execution-plan.md`](./execution-plan.md)
- **Moved:** here from the repo root on 2026-11-13; document paths in the body were updated to match
- **Branch:** `valuation-v3-fee-anchor`
- **Executed:** 2026-11-10; reviewed and revised 2026-11-11
- **Status (2026-11-13):** reviewed, brought up to current `main`, migration renumbered to `0112`, and the fee anchor switched off by default — see §11, which supersedes §1–§10 where they differ. Earlier status: Phases B, C and D implemented and verified locally. Phase A production access, the production calibration (B7) and the production outcome report (B10.5) were **not run**: no production `DATABASE_URL` was available in this environment. Migration `0111` is committed on its own branch for a migration-only pull request (see Round 2). The feature branch is otherwise uncommitted.

## 1. What changed, in one paragraph

The fair-value model is now `market-v3`: after the comparable-market stage and before the release-clause cap it applies a **bounded last-fee anchor** from the player's own last permanent fee, weighted by source, basis, recency and pre-move evidence. Staff can **record a transfer fee with its source** from the admin player page; those rows live in `player_transfers` with `vendor = 'manual'` (migration `0111`), survive the vendor sync, and win over the vendor's figure for the same move. The API exposes the anchor and the fee's provenance, and the UI shows the anchor as a driver (or why it was not used).

## 2. Phase A — environment and baseline (not completed)

| Plan step | Status |
|---|---|
| A1. Local backend/frontend environment | Done. Backend runs in the `transferx` conda env; frontend dependencies installed with `npm ci` (326 packages) |
| A2. Baseline test suite | Not captured against the plan's baseline. The suite was run only after implementation (results in §6) |
| A3/A4. Production access and read-only checks | **Not done.** No production `DATABASE_URL` was supplied |
| A5. Baseline production backtest | **Not run** (needs production) |
| B7. Production calibration | **Not run.** No constants were fitted or changed |
| B10.5. Production outcome report and user-reaction gate | **Not reached.** The report script is written and ready |

Because Phase A did not happen, the production numbers the plan expects in the model spec are left as an explicit `TODO` table rather than invented.

## 3. Phase B — `market-v3` last-fee anchor

### Model

`MODEL_VERSION_V2` is now `"market-v3"`. The version covers both the existing `market-v2` stages and the new Stage G2.

```text
fee_today    = last_fee_gbp × (1 + 0.06) ^ years_since_fee
anchor_value = fee_today × age_ratio × performance_ratio × league_ratio
             × current contract factor × current availability factor

weight = source_credibility × basis_weight × recency_weight × evidence_weight
factor = exp(clamp(weight × ln(anchor_value / value_before), ln 0.70, ln 1.60))
fair_value = value_before × factor          (before the release-clause cap)
```

Constants added in `backend/app/valuation/constants_v2.py`:

| Constant | Value |
|---|---|
| `FEE_ANCHOR_SOURCE_CREDIBILITY` | `TRANSFERX` 1.00, `MANUAL` 0.80, `REPORTED` 0.65 |
| `FEE_ANCHOR_BASIS_WEIGHT` | `PERMANENT` 1.00, `RELEASE_CLAUSE` 0.40 |
| `FEE_ANCHOR_RECENCY_YEARS` | 3.0 (`1 / (1 + years / 3)`) |
| `FEE_ANCHOR_FULL_EVIDENCE_MINUTES` | 1800 |
| `FEE_ANCHOR_MIN_EVIDENCE_MINUTES` | 450 |
| `FEE_ANCHOR_UNKNOWN_EVIDENCE_WEIGHT` | 0.60 |
| `FEE_ANCHOR_MIN_WEIGHT` | 0.25 |
| `FEE_ANCHOR_FACTOR_BOUNDS` | (0.70, 1.60) |
| `FEE_ANCHOR_PERF_EXPONENT` / bounds | 0.5 / (0.80, 1.60) |
| `FEE_ANCHOR_LEAGUE_EXPONENT` / bounds | 0.25 / (0.90, 1.10) |
| `FEE_ANCHOR_OUTGROWN_*` | max age 24, min 2 years, score gain 15 |

Skip rules, each with a plain-English reason on the result:

- no fee, or a fee of zero / unparseable (free, loan, undisclosed);
- fewer than 450 known minutes before the move;
- weight below 0.25;
- outgrown fee: age ≤ 24, at least 2 years since the move, score up at least 15 points since.

The anchor is a visible driver (`fee_anchor`, "Last fee anchor ×N") when applied, and an unapplied driver with the reason when not. It is persisted in `inputs_json["fee_anchor"]`, and `compute_valuation_v2(..., use_fee_anchor=False)` reproduces the pre-change `market-v2` result; a test asserts it.

### Code

| File | Change |
|---|---|
| `backend/app/valuation/constants_v2.py` | Version bump and the constants above |
| `backend/app/valuation/inputs_v2.py` | `LastFee` gains `basis`, `age_at_transfer`, `score_at_transfer`, `minutes_at_transfer`, `league_coefficient_at_transfer`, `fee_display`, `from_team`, `to_team`; `FeatureSetV2.last_fee` |
| `backend/app/valuation/engine_v2.py` | `FeeAnchor` result type and `fee_anchor()` (Stage G2); orchestration applies it after market rate, before the clause cap; `use_fee_anchor` switch |
| `backend/app/valuation/features_v2.py` | `build_last_fee()` builds the pre-move snapshot from the season before the transfer (`reference_season`); `get_features` loads the fee when not supplied; the comparables index excludes release clauses and vendor rows shadowed by a manual row |
| `backend/app/valuation/service.py` | Batch run loads all last fees once, counts `fee_anchored`, stores `fee_anchor` in `inputs_json`, exposes it on the response |
| `backend/app/valuation/schemas.py` | `FeeAnchorInfo`; `fee_anchor` on `FairValueSignal`; `source_note`/`basis` on `LastTransfer`; source comment includes `Manual` |
| `backend/app/players/last_fee.py` | Staff rows: `source: "Manual"`, `source_key: "MANUAL"`, `basis` and `source_note`; a manual row suppresses a vendor row for the same move (dates within 60 days) |
| `backend/scripts/valuation_backtest.py` | Repeat-transfer comparison: `v2_market` vs `v3_anchor` (n, median \|error\|, ±25%, ±50%, bias), split by anchor applied / not applied, plus skip reasons |
| `backend/scripts/valuation_outcome_report.py` | **New.** Read-only Markdown report: each named player's `market-v2` value, `market-v3` value, real last fee and reason; `--players`, `--also`, `--out`, `--summary-only` |

The backtest's `v3_anchor` path uses `build_last_fee(..., as_of=<later transfer>)`, so an earlier fee is seen as it would have been on the later transfer's date. A player's own move is not used as its own comparable.

## 4. Phase C — staff-entered transfer fees

| Area | Change |
|---|---|
| Schema | Migration `0111_manual_transfer_fees.py`: `player_transfers.fee_basis` (20), `source_note` (500), `source_url` (512), `entered_by_user_id` (FK `users.id`, `ON DELETE SET NULL`). Additive and nullable |
| Model | `PlayerTransfer` mirrors the four columns; docstring says vendor plus staff rows |
| Vendor sync | `vendor/history.py` deletes only `vendor = 'api_sports_v3'` rows, so a staff row survives a refresh |
| Cache freshness | `players/router.py` checks the transfer cache's age against vendor rows only, so a just-added staff row cannot suppress the vendor refresh |
| Last-fee lookup | A manual row within 60 days of a vendor row for the same player suppresses the vendor row; otherwise newest date wins; a completed TransferX deal still wins by date |
| Comparables | Manual rows enter as `REPORTED` (no extra weight); release-clause rows are excluded as comparables |
| Admin API | `GET /admin/players/{player_id}/transfer-fees` (all vendors, newest first), `POST` (201; validation; audit; recompute), `DELETE /admin/players/{player_id}/transfer-fees/{transfer_id}` (204; manual rows only; audit; recompute). All superuser-only |
| Validation | Amount > 0 and ≤ 500,000,000; currency GBP/EUR/USD; date not in the future; clubs 1–200 chars; basis `PERMANENT`/`RELEASE_CLAUSE`; source note 5–500 chars; source URL http(s) and ≤ 512 chars |
| Audit | `admin.player.transfer_fee_added` / `admin.player.transfer_fee_removed`, with actor, player, amount, currency, date, clubs, basis, note and URL |
| Recompute | Both add and delete call `compute_and_store_valuation`, so the anchor and the ledger reflect the change immediately (ineligible players return `None` and are unaffected) |
| Display formatting | `format_fee_display()` writes the vendor shape (`£ 105M`, `€ 4.5M`, `€ 750K`); the round trip through `fee_gbp()` is tested for GBP/EUR/USD at 750k, 4.5m and 105m |

## 5. Phase D — frontend and documentation

### Frontend

| File | Change |
|---|---|
| `frontend/src/types/api.ts` | `FeeAnchorInfo`; `fee_anchor` on `FairValueSignal`; `source_note`/`basis` on `LastTransfer`; `source` includes `Manual`; comments updated to `market-v3` |
| `ValuationBreakdownPopover.tsx` | The applied anchor renders through the existing driver rows; when not applied and a last transfer exists, a muted line says `Last fee not used: {reason}`. Footer disclaimer untouched. Header comment updated |
| `ledger/FactsStrip.tsx` | The "Last transfer" cell appends the source (`API-Football` / `TransferX` / `Manual`) and puts `source_note` in the cell's `title` |
| `pages/admin/AdminPlayerDetailPage.tsx` | New "Transfer fees" card: table (date, move, fee, source, note with optional source link, Remove on manual rows only) and an add form (amount, currency, date with `max=today`, basis, from, to, source note, source URL). On success it invalidates the fee list, `["valuation"]` and the player's ledger |
| Tests | `ValuationBreakdownPopover.test.tsx` (`market-v3` fixture, anchor step, "not used" reason, v1 unchanged); `FactsStrip.test.tsx` (API-Football and Manual sources, `title` note); new `AdminPlayerDetailPage.test.tsx` (lists both vendors, exactly one Remove, exact POST body, DELETE path) |

Copy follows the rules: "Last fee anchor", "Last transfer", "last reported fee", "TransferX model". No "true value", "real value", "overpriced" or "bargain".

### Documentation

| File | Change |
|---|---|
| `docs/feature_spec/valuation/market-data.md` | Status → "Phase 1 implemented (simplified) 2026-11-10; Phases 2–4 not built"; new "What was built, and how it differs from this spec" |
| `docs/feature_spec/valuation/model.md` | Stage G2 in formula and stage table; full anchor rules; `market-v3` note; pending production backtest table with explicit `TODO` |
| `docs/CHANGELOG.md` | `market-v3`, the admin fee card, and the vendor-sync fix under `[Unreleased]` |
| `docs/IMPLEMENTATION_STATUS.md` | Valuation row updated; gap for the missing production backtest |
| `docs/engineering/api-reference.md` | `fee_anchor` / `last_transfer` provenance on `/valuation`; the three `/admin/players/{id}/transfer-fees` endpoints |
| `docs/architecture/data-model.md` | Four `player_transfers` columns and `vendor = 'manual'`; staff-fee rule |
| `docs/business/glossary.md` | "Fair value" → `market-v3`; new "Last fee anchor" |
| `docs/SESSION_HANDOVER.md` | Session summary and what is left |

## 6. Verification

| Check | Result |
|---|---|
| `pytest tests/test_admin_transfer_fees.py tests/test_last_fee.py tests/test_valuation_v2.py tests/test_valuation.py` | **119 passed** in 42s |
| Full backend suite | **974 passed, 1 failed.** The failure is pre-existing and unrelated: `tests/test_real_world.py::test_playing_on_for_the_old_club_is_for_staff_and_cant_be_applied` raises `ValueError: Invalid format string` at `app/players/real_world.py:349`, because `strftime("%-d %b %Y")` is unsupported on Windows. That file is untouched by this work and the format is valid on Linux/Railway |
| `npx tsc -b` (frontend) | 0 errors |
| `npx vitest run` (frontend) | 431 passed, 1 failed: `PlayerMarketPage.test.tsx` "Show more requests page 2 and appends it" timed out at 5s under full-suite load. Re-run alone: **12/12 passed**. Untouched file; load flake |
| Ruff on changed files (`E501,F401,F841,E9`) | No new findings. The full-repo run is noisy with pre-existing findings because the project config sets only line length and target version |
| Manual fee end to end | Covered by `test_admin_transfer_fees.py`: add → last transfer with source → anchor applied → survives `refresh_transfers` → delete restores the vendor figure; vendor rows cannot be deleted |
| Audit | One row per add and per delete, with actor and values |
| Permissions | Admin endpoints superuser-only; the existing valuation permission tests still pass |
| Replay | Extended `test_v2_row_replays_exactly_from_inputs_json` with a fee: `fee_anchor.applied` is true and reproduces exactly |
| No regression without a fee | `test_use_fee_anchor_false_reproduces_v2` and the untouched hard-coded expectations pass |

### Acceptance checklist from the plan

| # | Check | Status |
|---|---|---|
| 1 | Backend suite | 974/975; the one failure is the pre-existing Windows `strftime` issue above |
| 2 | Lint | No new findings in touched files |
| 3 | Frontend | `tsc` green; 431/432 with one load flake that passes alone |
| 4 | Replay | Pass |
| 5 | No regression without a fee | Pass |
| 6 | Production backtest | **Not run** — no production `DATABASE_URL` |
| 7 | Bounds | Asserted in tests; no production CSV to scan |
| 8 | Outcome report | Script written (read-only); **not run against production** |
| 9 | Manual fee end to end | Pass |
| 10 | Audit | Pass |
| 11 | Permissions | Pass |
| 12 | Copy review | Pass |
| 13 | Docs | Done |

## 7. Not done, and why

1. **Phase A production access.** No `DATABASE_URL` was provided, so nothing ran against production. The only scripts that may run against Railway in that situation are the two read-only ones (`scripts.valuation_backtest`, `scripts.valuation_outcome_report`); no write script, migration, daily refresh, recompute, seed, backfill or repair script was run, and no database URL was written to a file, commit or log.
2. **B7 calibration and B10.5 user gate.** Without the production backtest there was nothing to calibrate and no outcome report for the product owner to react to. No constants were fitted; the defaults above are the plan's starting values.
3. **Phases 2–4 of the market-data spec** (licensed provider values, consensus, valuation stack) are not built. PlayerElo remains the recommended pilot.
4. **No `player_valuations` fee columns.** The anchor is stored in `inputs_json`, which replays the row exactly; the plan's optional denormalised columns were not added.
5. **Feature flag.** None; the version string is the switch. `compute_valuation_v2(..., use_fee_anchor=False)` is the code-level fallback.
6. **Not committed.** The user has not asked for a commit.

## 8. How to finish the production side (corrected 2026-11-11)

The commands originally written here **cannot run before migration `0111` is deployed**: the
feature branch's ORM maps four `player_transfers` columns that production does not have, so every
`select(PlayerTransfer)` fails with `UndefinedColumnError`. The product owner chose Route 1 — ship
the migration first, then run the scripts from this working tree.

1. Push `migration-0111-manual-transfer-fees` and open the pull request (see Round 2); the user
   merges and Railway applies `0111` on start.
2. Run the read-only S4 check (four columns present, `alembic_version = 0111`).
3. With a production `DATABASE_URL`, `JWT_SECRET_KEY` and `PYTHONUTF8` set, from `backend/`:

```powershell
& $conda run --no-capture-output -n transferx python -m scripts.valuation_backtest `
    --csv $env:TEMP\backtest.csv
& $conda run --no-capture-output -n transferx python -m scripts.valuation_backtest --grid
& $conda run --no-capture-output -n transferx python -m scripts.valuation_outcome_report `
    --players "Haaland,Ronaldo,Rice,Palmer,Yamal,Bellingham,Saka" `
    --also 6 `
    --out $env:TEMP\valuation_outcome_report.md
Remove-Item Env:DATABASE_URL
```

- Keep every output in the scratch/temp directory, never the repo root.
- The backtest prints the repeat-transfer table (`v2_market` vs `v3_anchor`), the anchor-applied
  sample and rows, the skip reasons and the 16-row calibration grid; fill the `TODO` table in
  `docs/feature_spec/valuation/model.md` from it.
- The outcome report is the document for the product owner (B10.5). Review it before any recompute.
- **Do not** run `alembic`, `daily_refresh`, `recompute_valuations*`, seed, backfill or repair
  scripts against Railway without an explicit instruction; recomputing production is a write.
- After deploying the feature, the next daily recompute writes `market-v3` rows.
  `scripts/recompute_valuations_railway.py` forces it sooner, but only on an explicit request.

## 9. Rollout notes (D3)

1. Merge to `main`; Railway deploys and applies migration `0111` on start.
2. Old valuation rows stay (append-only). Each player shows the `market-v3` build-up once his row is newer than the last one.
3. The daily recompute writes `market-v3` from then on. Forcing it is a production write and needs an explicit instruction.
4. After the recompute, re-run the outcome report and compare with the pre-deploy report.

## 10. Round 2 — review fixes, 2026-11-11

The review in `docs/feature_spec/valuation/execution-plan.md` (Addenda 1 and 2) found 14 issues; the production gate
had been skipped and several model and copy defects needed fixing before any `market-v3` row is
stored. This round made those fixes locally.

### Migration-only pull request (S3)

- Worktree: `$env:TEMP\tx-migration-0111`, branch `migration-0111-manual-transfer-fees`, based on
  `origin/main` at `e7e2453` (still migration `0110`).
- Commit `7778515` — "Migration 0111: staff-entered transfer fee columns (additive, ahead of the
  code)". **One file only**: `backend/migrations/versions/0111_manual_transfer_fees.py`.
- The docstring now says the staff rows "will survive the vendor sync once the code that reads
  these columns is deployed"; the copy in the feature tree was changed identically (S6).
- **Not pushed and no pull request yet:** this environment has no `gh` and the HTTPS remote needs
  interactive GitHub credentials. Push from the worktree with
  `git push -u origin migration-0111-manual-transfer-fees`, then open a PR from the compare link.
  The user merges; the agent does not.

### Code and tests (R2–R7)

| Item | Change |
|---|---|
| R3 — a later free move | `last_fee.py` records `later_free_move` (newest permanent `Free` row more than 60 days after the winning fee). `LastFee` carries it, `build_last_fee` passes it through, and `fee_anchor` skips first with "He has moved on a free transfer since the {year} fee". Loans, "N/A" and free moves before the fee do not trigger it; the "Last transfer" display is unchanged |
| R4 — honest skip reasons | When weight < 0.25, the reason names the smallest of basis, evidence, recency and source, in that tie order. A recent fee skipped for thin evidence is no longer called "too old" |
| R5 — calibration | `fee_anchor` gains `source_credibility` and `recency_years` keyword overrides that default to the constants. The backtest prints the anchor-applied n (under 15 → keep defaults), the applied rows, and `--grid`: 16 settings of REPORTED credibility {0.50, 0.65, 0.80, 0.90} × recency {2, 3, 4, 5}, with `v2_market` recomputed on each setting's applied rows |
| R6 — report | The 10 largest rises and 10 largest falls among anchor-applied players, a min/max factor line against the bounds, a coverage sentence, tiered name matching (whole name → whole word → substring), "also matched" capped at 5 plus "and N more", and `SET TRANSACTION READ ONLY` on the backtest too |
| R7 — test gaps | The Appendix B worked example is computed from the real constants; the staff-fee round trip also asserts `engine_v2.parse_fee` reads the display string; the comparables "earlier fee" lookup carries a comment recording that it ignores the manual-shadow rule and treats every earlier fee as REPORTED/PERMANENT |
| R9 — frontend | The note is labelled "Source note (shown to clubs)"; a muted hint says the source URL is admin-only; Remove asks for confirmation ("Remove this fee? His model value is recalculated straight away.") before deleting |
| R10 — docs | Model and market-data specs, changelog; the log's former §8 corrected above |

### Verification

| Check | Result |
|---|---|
| `pytest tests/test_valuation_v2.py tests/test_last_fee.py tests/test_valuation_outcome_report.py tests/test_admin_transfer_fees.py tests/test_valuation.py` | **134 passed** in 45s |
| `npx tsc -b` | 0 errors |
| `npx vitest run src/pages/admin/AdminPlayerDetailPage.test.tsx` | 3 passed, including the new confirmation step |
| Ruff on changed files (`E501,F401,F841,E9`) | No new findings. The 16 remaining `E501` hits are pre-existing long lines in `last_fee.py` and `test_last_fee.py`, untouched by this round |

### Still open

- **S4/S5 — production verification and gate.** Needs the user to merge the migration pull request
  and supply a production `DATABASE_URL`. Then: confirm the four columns and version `0111`, run
  the backtest, `--grid` and the outcome report to `$env:TEMP`, show the user, and ask section
  11.5's three questions. No merge, recompute or tuning before the answers.
- **R10 production figures.** `valuation/model.md`'s backtest table stays `TODO` until S5; no
  figures have been invented.
- **S6.** After the migration merge, delete the feature tree's untracked copy and bring
  `origin/main` in, so the feature diff contains no migration.
- The feature branch and all of this round's changes remain uncommitted.

## 11. Round 3 — review and make-safe, 2026-11-13

A second reviewer checked Rounds 1–2 against the plan and against `origin/main`, with the aim of a change that is safe to deploy the same day. Plan Addendum 3 records the decisions; this section records what was found and done. **Where this section disagrees with §1–§10, this section is current.**

### Found

| # | Finding | Severity | Outcome |
|---|---|---|---|
| 1 | **Migration id collision.** `main` gained `0111_move_reminders.py` on 2026-11-12. This tree's `0111_manual_transfer_fees.py` also declared `revision = "0111"`, `down_revision = "0110"`: two revisions with one id, and the API container's `alembic upgrade head` would have failed at start | Blocking | Renamed to `0112_manual_transfer_fees.py`, `revision = "0112"`, `down_revision = "0111"`. `alembic heads` → `0112 (head)`; `alembic upgrade 0111:0112 --sql` renders four `ADD COLUMN`s and the foreign key |
| 2 | **The branch was 29 commits behind `main`** (base `5efa8d7`; `main` at `15e6ba1`, 283 files changed, including a design-system guard test) | Blocking | Fast-forwarded and re-applied the work. Conflicts in `FactsStrip.tsx` (kept `main`'s type roles, added the `title`) and five docs (both sides kept in the changelog; `main`'s dates and handover kept, then updated) |
| 3 | **The new frontend failed `designSystem.test.ts`**: 10 raw sizes and one uppercase label in `AdminPlayerDetailPage.tsx`, one raw size in `ValuationBreakdownPopover.tsx` | Blocking (red suite on `main`) | Moved to `text-caption` / `text-small` / `text-input lg:text-body`. Allowlist stays empty |
| 4 | **The production gate is still not run.** The env file supplied (`ATT95143.env`) holds a `DATABASE_URL` pointing at `db:5432`, the local Docker service name, and this machine has no Docker. There is still no production access | Blocking for the model change | The anchor ships **switched off** (below). Nothing was run against any database |
| 5 | The migration-only pull request (S3) was never pushed; commit `7778515` exists only locally and is now misnumbered | Plan drift | Route 1 dropped; the migration ships with the code. The branch `migration-0111-manual-transfer-fees` and the worktree at `%TEMP%\tx-migration-0111` are stale and were left untouched |
| 6 | `ATT95143.env` is untracked and **not** matched by `.gitignore` (`.env`, `.env.local` only). It holds API keys and secrets | Hazard | Not committed, not edited. Do not `git add -A` on this tree |
| 7 | The admin card's subtitle said "The last fee anchors his model value", which is untrue while the anchor is off | Copy | Now "The newest fee is his last transfer" |
| 8 | `fee_anchor` would raise on `log(0)` if an adjustment factor were ever zero | Low (no current path produces it) | Guarded: not applied |

Reviewed and accepted as built: the engine against B3/R3/R4 (rule order, weights, bounds, reasons); `last_fee.py` (chunking, manual-shadow rule, `later_free_move`); the comparables index (release clauses excluded, vendor rows shadowed by a staff row, own transfers never price the player); the admin endpoints (superuser only, audited, validation); the vendor-sync and cache-freshness fixes; replay from `inputs_json`; both scripts are read-only (`SET TRANSACTION READ ONLY`, no `add`/`flush`/`commit`). `/players/market/{id}/ledger` returns the lookup row as-is, so it now also carries `source_key`, `basis` and `later_free_move`; harmless, and the typed valuation endpoints drop them.

### The switch

- `VALUATION_FEE_ANCHOR_ENABLED`, default `false` (`backend/app/config.py`, `.env.example`).
- Off: `service.compute_and_store_valuation` passes no fees to the feature provider, so the engine's no-fee path runs. The row's value, drivers and replay are `market-v2`; `model_version = "market-v2"`; `inputs_json["fee_anchor"]` and `["features"]["last_fee"]` are `null`; the batch job does not load fees and reports `fee_anchored: 0`.
- On: as §3 describes; `model_version = "market-v3"`.
- Not affected by the switch: staff-entered fees and their audit, the "Last transfer" cell with its source, the sync fix, and both read-only scripts (they call the engine directly).
- Tests run with it on (`tests/conftest.py`); `test_fee_anchor_switched_off_stores_a_market_v2_row` covers off, including the replay and the API response.

### Files touched in this round

`backend/migrations/versions/0112_manual_transfer_fees.py` (renamed), `backend/app/config.py`, `.env.example`, `backend/app/valuation/constants_v2.py`, `service.py`, `engine_v2.py`, `backend/app/players/models.py` (comment), `backend/tests/conftest.py`, `backend/tests/test_valuation_v2.py`, `frontend/src/pages/admin/AdminPlayerDetailPage.tsx`, `frontend/src/components/players/ValuationBreakdownPopover.tsx`, `frontend/src/components/players/ledger/FactsStrip.tsx`, and the docs: changelog, implementation status, product spec, glossary, data model, API reference, both valuation specs, environments and deployment, session handover, the plan (Addendum 3).

### Verification

| Check | Result |
|---|---|
| `pytest tests/test_valuation_v2.py tests/test_last_fee.py tests/test_valuation_outcome_report.py tests/test_admin_transfer_fees.py tests/test_valuation.py` | **135 passed** |
| Full backend suite (Windows) | **997 passed, 7 failed.** All seven are the same Windows-only error in code this work does not touch: `strftime("%-d …")` raises `ValueError: Invalid format string` on Windows and is valid on Linux/Railway. Six are in `tests/test_move_reminders.py` (`app/reminders/service.py:389`, new on `main` since Round 2) and one is the known `tests/test_real_world.py` case (`app/players/real_world.py:349`). Not run on Linux here |
| `npx tsc -b` | 0 errors |
| `npx vitest run` (whole frontend) | **490 passed**, 67 files, including `designSystem.test.ts` |
| `ruff check --select F,E9` on touched backend files | Clean |
| `alembic heads` | `0112 (head)` |

### Acceptance checklist, as it stands

| # | Check | Status |
|---|---|---|
| 1–5, 9–15, 19 | Suites, lint, replay, no-fee regression, staff fee end to end, audit, permissions, copy, docs, free move, skip reasons, clean tree | Pass |
| 6, 7, 8, 16, 17, 18 | Production backtest, bounds on production, outcome report, calibration evidence, figures in the docs, gate honoured | **Open** — no production access. The anchor is off until they pass |
| 20–22 | Migration-only pull request | Dropped (Addendum 3) |
| 23–25 | One head; off means `market-v2`; design guard | Pass |
| 26 | Switch turned on only after the gate | Open by design |

### Rollout (replaces §8 and §9)

1. Commit on `valuation-v3-fee-anchor` and open one pull request to `main`. Leave out `ATT95143.env`, `conversation.jfif` and `docs/presentations/` unless the user wants them.
2. Merge away from the 17:00 and 22:00 UK refreshes. Railway deploys; the API applies `0112` at start. The `stats-worker` does not migrate and reads the new columns, so it must not run a refresh before the API is up.
3. Production numbers do not change: the anchor is off. Staff can record fees straight away.
4. Read-only, with a production `DATABASE_URL` in the session's environment only: `scripts.valuation_backtest --csv`, `--grid`, and `scripts.valuation_outcome_report`, outputs to the temp directory.
5. Show the product owner; record the answers to the plan's three questions here; fill the `TODO` table in `docs/feature_spec/valuation/model.md`.
6. Set `VALUATION_FEE_ANCHOR_ENABLED=true` on `backend` and `stats-worker`. `market-v3` rows appear from the next daily recompute.

## 12. Round 4 — review fixes before merging, 2026-11-22

A review of the pull request (#77) asked for these changes before it merged. **Where this section disagrees with §1–§11, this section is current.**

| # | Finding | Done |
|---|---|---|
| 1 | **Migration id collision, again.** `main` gained `0112_move_stalled_notification` and `0113_term_counters` after Round 3, so `0112_manual_transfer_fees` gave Alembic two heads (`alembic heads` printed `0112` and `0113`) and the deploy's `alembic upgrade head` would have failed | Renamed to `0114_manual_transfer_fees.py`, `revision = "0114"`, `down_revision = "0113"`. `alembic heads` → `0114 (head)`. Upgraded, downgraded and upgraded again on a copy of the local database |
| 2 | **The staff note was public.** `source_note` was in `last_transfer` on the player ledger, which signed-out visitors can call, and on `/valuation/players`. The player page showed it as a tooltip. A note may hold internal remarks | The note and URL never leave the admin endpoints. `last_transfer.source` reads **"Staff-entered"** (was "Manual"). The admin form's label is "Source note (staff only)". Tests check that neither the public ledger nor the valuation carries it |
| 3 | **The admin fee endpoints turned every error into a 400** with the exception's text | They catch `ValueError` only; anything else is a 500 |
| 4 | Fees stored as display text lose precision and drift with exchange rates | **No change.** Six significant figures is about £100 on a £41m fee, and `GBP_PER` holds fixed rates, applied the same way to API-Football's fees |
| 5 | `compute_valuation_v2(use_fee_anchor=True)` by default | The engine's default stays on, so a stored row replays from its own inputs: a row with a last fee was anchored. `service.compute_and_store_valuation` now passes the setting explicitly, as a second guard beside not loading the fee |
| 6 | Removing a staff fee needed no reason | `DELETE /admin/players/{id}/transfer-fees/{fee}` takes `{"reason"}` (5 to 500 characters), recorded in the audit event. The admin page asks for it in the standard reason dialog |
| 7 | Links to the moved valuation specs | One link on `main` pointed at the old path (`leagues-and-club-teams`); fixed. No relative link in `docs/` is broken |

### Outcome report on local data (2026-11-22)

`scripts.valuation_outcome_report`, read-only, against a copy of the **local** database (an older snapshot than production):

- **Coverage:** 1,113 players valued. 124 have a last fee, and the anchor applied to 54.
- **Effect:** 40 players moved by more than 10%. The median change where applied was −7.2%. Factors span the full bounds, ×0.70 to ×1.60.
- **Repeat-transfer backtest, anchor-applied rows (n = 10, under the plan's 15):**
  - accuracy within 25% stays at 40%;
  - the median bias worsens from −8.4% to **−24.5%**.
- **The largest falls come from data, not the method:**
  - fees the snapshot has as the latest when a later, larger move exists (Ekitike, Isak);
  - an apparent loan fee read as a sale (Xavi Simons);
  - fees that were cheap for a reason (an expiring contract, for example).

**Recommendation:** merge with the anchor **off**, as Round 3 decided. Staff can then correct the fees the report shows are wrong. Run the report and backtest against production before setting `VALUATION_FEE_ANCHOR_ENABLED=true`. Steps 2 to 6 of the rollout above stand, with `0114` in place of `0112`.
