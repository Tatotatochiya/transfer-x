---
title: "Valuation: execution plan for market-v3 and staff-entered fees"
last_updated: 2026-11-13
status: Built and reviewed; Addendum 3 says what ships and what is still open
owner: "TODO — assign a Product Owner"
---

# Valuation Execution Plan — last-fee anchor (`market-v3`), staff-entered fees, outcome report

| | |
|---|---|
| Written | 2026-11-10 |
| Status | Built and reviewed; see Addendum 3 (2026-11-13) for what ships and what is still open |
| Audience | An engineer or coding agent who has never seen this repository |
| Brief | [`brief.md`](./brief.md) |
| Log | [`execution-log.md`](./execution-log.md) |
| Moved | Here from the repo root on 2026-11-13; document paths in the body were updated to match, including in commands written before the move |
| Design background | `docs/feature_spec/valuation/market-data.md`, `docs/feature_spec/valuation/model.md`, `docs/feature_spec/valuation/report-sample.md` |

Read sections 1–4 once, then execute sections 5–9 in order. Section 10 is the acceptance checklist. Section 11 is the report the product owner will actually look at.

---

## 1. Background

### 1.1 The product

TransferX is enterprise software for professional football transfers: clubs, agents and players run a transfer end to end (listings, offers, deal room, paperwork). Alongside every player the product shows a **fair value**: TransferX's own deterministic, explainable estimate of what the player is worth. It is sold as an *independent second opinion*, never as "the true value".

- **Stack:** FastAPI + SQLAlchemy (async) + Alembic + PostgreSQL in `backend/`; React 19 + Vite + TypeScript + Tailwind v4 in `frontend/`.
- **Data:** player stats, fixtures, injuries and transfer history come from **API-Football** (paid, licensed), synced by `backend/app/jobs/daily_refresh.py`.
- **Production:** Railway. Migrations are applied automatically when the API container starts (`backend/entrypoint.sh`).
- **Docs:** start at `docs/PRODUCT_SPEC.md`. Repo skills in `.claude/skills/` (`engineering-standards`, `documentation-standards`, `session-lifecycle`, `product-principles`) describe house rules — follow them.

### 1.2 The problem

Demo feedback on 30 October 2026: the model showed Declan Rice at about £45m when Arsenal paid about £100m for him, and Cole Palmer at £33m against a £40m fee. The audience knows the real fees, so one unexplained low number destroys trust.

Measured on production (17 Oct 2026, 84 fee-bearing transfers): 26–31% of fees predicted within ±25%; fees of £25m+ under-predicted by 37%.

### 1.3 Constraints (all decided — do not reopen)

| Constraint | Detail |
|---|---|
| **No scraping** | Transfermarkt and similar sites forbid it and the data is legally protected. `backend/app/enrichment/transfermarkt.py` is a dev-only prototype blocked in production by `enrichment/registry.py`. Do not touch or use it |
| **No new paid vendor now** | Sportmonks is too expensive for a startup, and it has no market-value field anyway (only transfer `amount`). See 3.3 for the cheapest future option |
| **Fair value stays independent** | Never overwrite or silently blend the model with a third-party number |
| **Estimate, never a verdict** | Copy rules: say "TransferX model", "last reported fee". Never "true value", "real value", "overpriced", "bargain", or imperatives |
| **Permissions unchanged** | Player accounts get 403 on valuation endpoints; private players 404 |
| **Append-only history** | `player_valuations` rows are never rewritten; a new model version writes new rows |
| **Reproducible** | Every stored valuation must be rebuildable exactly from its own `inputs_json` |

### 1.4 Decisions made with the product owner on 2026-11-10

| Question | Decision |
|---|---|
| Paid market-value provider | None in this plan. PlayerElo is documented as the next step |
| How to store staff-entered fees | Minimal: manual rows in the existing `player_transfers` table. **Not** the `transfer_fee_observations` model in the spec |
| Environment on this machine | A conda env with Python 3.12. No Docker |
| Real-player data for the outcome test | Railway production database, **read-only** |

---

## 2. What exists today (verified in the code on 2026-11-10)

### 2.1 The last fee is already shown — do not rebuild it

`backend/app/players/last_fee.py`:

- `fee_gbp(display)` parses API-Football fee strings (`"€ 116.6M"`, `"£40M"`, `"&pound; 40M"`, `"500K"`; no currency sign means euros) into pounds using static rates `GBP_PER = {"EUR": 1.17, "USD": 1.33}` from `valuation/features_v2.py`. Returns `None` for `"Free"`, `"Loan"`, `"N/A"`.
- `last_transfer_fees(db, player_ids) -> {player_id: {"fee_gbp", "fee_display", "date", "from", "to", "source"}}`. Newest permanent move with a known fee wins. Sources: `player_transfers` rows (`source: "API-Football"`) and completed permanent TransferX deals that are not demo/test (`source: "TransferX"`, filtered through `app.demo.service.shared_deals`).

Consumers: `valuation/router.py` (single and batch endpoints set `resp.last_transfer`), `players/router.py` (`/players/market/{id}/ledger`), `lite/service.py`, `demo/house.py`. Frontend: `components/players/ledger/FactsStrip.tsx` ("Last transfer" cell), `components/players/PlayerListRow.tsx`, `pages/lite/LiteBuyPage.tsx`. Tests: `backend/tests/test_last_fee.py`.

### 2.2 The valuation model (`market-v2`)

```
fair_value = anchor[position] × league_coefficient × curve(performance)
           × age_factor × potential × trajectory × form
           × contract × availability × market_rate
           (capped at a published release clause)
```

| File | Role |
|---|---|
| `backend/app/valuation/constants_v2.py` | Every tunable. `MODEL_VERSION_V2 = "market-v2"` (line 14), `FEE_INFLATION_PER_YEAR = 0.06`, `COMPS_SOURCE_WEIGHTS`, `MARKET_FACTOR_BOUNDS = (0.65, 1.60)` |
| `backend/app/valuation/inputs_v2.py` | Plain dataclasses, no ORM: `SeasonFeatures`, `RecentGame`, `FeatureSetV2`, `CompRecord`, and `features_from_snapshot()` (rebuilds a `FeatureSetV2` from stored JSON) |
| `backend/app/valuation/engine_v2.py` | **Pure** functions. `compute_valuation_v2(fs, comps=None, now=None, *, market=None) -> ValuationOutcomeV2`. Each factor is appended as a `Driver(key, label, detail, factor, value_after)` through the inner `step()` helper. Reusable pieces: `age_factor`, `contract_factor`, `availability_factor`, `performance_evidence`, `league_coefficient`, `intrinsic_value`, `market_rate`, `clamp` |
| `backend/app/valuation/features_v2.py` | DB side. `MarketFeatureProvider.get_features(db, player)`; `build_seasons(..., up_to_season=)`; `reference_season(date)`; `_age_at(player, on, today)`; `build_comparables_index(db)` (every fee-bearing permanent transfer in the last 3 years, as `CompRecord`s) |
| `backend/app/valuation/service.py` | `compute_and_store_valuation(db, player, comps=None)` writes a `PlayerValuation` row with `inputs_json = {features, breakdown, drivers, market, factors}`; `compute_all_valuations(db)` is the daily batch; `build_valuation_response(row, reference_price)` builds the API response from a stored row |
| `backend/app/valuation/schemas.py` | `ValuationResponse` (has `drivers`, `comparables_used`, `last_transfer`), `LastTransfer`, `ValuationDriver` |
| `backend/app/valuation/router.py` | `GET /valuation/players/{id}`, `GET /valuation/players?ids=` |
| `backend/scripts/valuation_backtest.py` | Read-only backtest of v1 / v2 intrinsic / v2+market against real fees, leave-one-player-out |
| `backend/tests/test_valuation_v2.py` | Builders `_season()`, `_fs()`, `_comp()`; DB helpers `_player()`, `_stats()`; replay test `test_v2_row_replays_exactly_from_inputs_json` |
| `frontend/src/components/players/ValuationBreakdownPopover.tsx` | Renders `signal.drivers` (hides ×1.00 rows) and a mandatory disclaimer footer |

Key rule already in the engine: **a player's own transfers never price him** in the comparable-market stage (`market_rate` skips `comp.player_id == player_id`). The anchor in this plan is a separate, explicit, bounded stage; it does not weaken that rule.

### 2.3 Transfer history storage

`PlayerTransfer` (`backend/app/players/models.py:168`, table `player_transfers`): `player_id`, `vendor`, `transfer_date`, `transfer_type` (`"Transfer"`/`"Loan"`), `team_in_*`, `team_out_*`, `fee_display` (free text), `fetched_at`.

**Bug that blocks manual fees:** `backend/app/vendor/history.py:104` — `refresh_transfers` deletes *every* `PlayerTransfer` row for the player before re-inserting the vendor's list. Any staff-entered row would be wiped on the next sync. Fixed in step C2.

### 2.4 Admin pattern

`backend/app/admin/router.py`: endpoints use `Depends(get_current_superuser)` and record changes with `admin_audit.record(db, current_user, "<action>", entity_type=..., entity_id=..., description=..., details=...)`. The model to copy is `update_player` at line 678. Frontend admin pages live in `frontend/src/pages/admin/` (`AdminPlayerDetailPage.tsx`).

### 2.5 Things that look useful but are not

- `backend/app/enrichment/etv.py` points at `api.etv.football`, which did not resolve on 2026-10-31. Not a working integration. Ignore.
- `Player.market_value` is a legacy vendor field the fair value exists to be independent of. Do not feed it into the model.

---

## 3. Best options at this stage

### 3.1 Ranked

| # | Option | Cost | Legal risk | Expected effect | In this plan? |
|---|---|---|---|---|---|
| 1 | **Anchor the model to the player's own last fee**, adjusted for time, age, contract, form and availability, bounded and explained | Engineering only | None (data already licensed) | Removes the "obviously off" cases where a recent real fee exists; the fee becomes a visible driver | **Yes — Phase B** |
| 2 | **Staff fill in or correct fees by hand, with a source** | Engineering only | None | Closes the coverage gap (309 of 532 contracted players have a fee; the rest have none or "undisclosed") and fixes wrong vendor figures | **Yes — Phase C** |
| 3 | **Show provenance on the last fee** (source, and the staff note for manual entries) and the reason when the fee was *not* used | Small | None | Trust: no unexplained numbers | **Yes — Phase D** |
| 4 | **Prove it**: repeat-transfer backtest + named-player before/after report | Small | None | Lets the team judge quality before anything reaches a club | **Yes — B6, B7** |
| 5 | Re-run calibration after each transfer window as fees accumulate (`BASE_ANCHORS_V2`, small-league `LEAGUE_COEFFICIENTS`) | Small, recurring | None | Gradual accuracy gain; small leagues currently have 2–4 fees each, too few to fit | Follow-up (after January 2027 window) |
| 6 | Widen transfer-history sync to more players so the comparables index grows | API-Football quota (already paid) | None | More comparables → market-rate stage binds less on its bounds | Follow-up; check quota first |
| 7 | **PlayerElo** licensed market values, shown *beside* the model in admin-only shadow mode | ≈ €19–199/month (public pricing; Business tier carries the commercial licence) | Low if the licence is confirmed in writing | A live market cross-check; uses API-Football-compatible player IDs, so matching is cheap | **Next step, not built here** |
| 8 | SciSports ETV / Off The Pitch | Quote-only, likely five figures a year | Low with contract | Strongest coverage and methodology | Later, when budget allows |
| 9 | Sportmonks | €29–249/month | Low | **No market value in its schema** — transfer amounts only. Would duplicate API-Football | No |
| 10 | Transfermarkt / any reseller of scraped data | — | **High** | — | **Never** |

### 3.2 What "history" improves

- **Transfer history:** each fee gains a recorded source; staff can add missing moves' fees; manual rows survive the vendor sync.
- **Valuation history:** unchanged in shape (append-only). New rows carry `model_version = "market-v3"` and store the fee anchor (inputs, weight, factor, reason) in `inputs_json`, so any past number can be explained and replayed.

### 3.3 Honest limits of this plan

- The anchor only helps players **with** a usable fee. A player with no fee, a free transfer or an academy graduate (Yamal) is priced exactly as before.
- The anchor is **bounded (×0.70–×1.60) and weighted by how informative the fee still is**. Rice moves toward his fee; he does not jump to £100m. That is deliberate: a three-year-old fee is evidence, not the current price.
- API-Football reports fees; it does not verify them and does not flag release clauses (Haaland's 2022 move was one). Staff can correct such cases with a manual row.
- Pre-transfer stats exist from roughly the 2022 season on, so older fees are treated as weaker evidence and often not used.

---

## 4. Order of work

| Phase | Schema change | Notes |
|---|---|---|
| A. Environment | no | Nothing runs on this machine yet |
| B. Fee anchor, backtest, outcome report | **no** | Run the backtest and the report against production **before** starting C |
| C. Staff-entered fees | yes — migration `0111` | Once the ORM model has the new columns, read-only scripts fail against production until the migration is deployed there |
| D. Frontend, docs, final verification | no | |

Working rules:

- Branch: `git checkout -b valuation-v3-fee-anchor`. Commit only when the user asks. Do not touch the untracked files already in the tree (`conversation.jfif`, `docs/presentations/`, the two untracked specs) beyond the doc edits listed in D2.
- Small diffs, reuse what exists, no drive-by refactors. In particular, **do not merge the two fee parsers** (`engine_v2.parse_fee` and `last_fee.fee_gbp`) — out of scope.
- `ruff` line length is 100 (`backend/pyproject.toml`).

---

## 5. Phase A — Environment setup (Windows 10, PowerShell)

State of this machine on 2026-11-10: no `docker`; no `python` or `py` on PATH; no `.env`; no WSL distro; Node v24.15 present; conda at `C:\Aaron\Tools\Anaconda38\condabin\conda.bat` (base env is Python 3.8 — too old; the backend needs ≥ 3.12).

### A1. Create the Python environment

```powershell
$conda = "C:\Aaron\Tools\Anaconda38\condabin\conda.bat"
& $conda create -n transferx python=3.12 -y
& $conda run -n transferx python --version          # expect Python 3.12.x
& $conda run -n transferx python -m pip install --upgrade pip
& $conda run -n transferx python -m pip install -e "D:\Repo\transfer-x\backend[dev]"
```

Troubleshooting:

| Symptom | Fix |
|---|---|
| `PackagesNotFoundError: python=3.12` | Old conda. Try `& $conda create -n transferx -c conda-forge python=3.12 -y`. If that fails, `& $conda update -n base conda -y` and retry |
| Still no 3.12 | Install Python 3.12 from python.org (tick "Add to PATH"), then `python -m venv D:\Repo\transfer-x\backend\.venv` and use `D:\Repo\transfer-x\backend\.venv\Scripts\python.exe` wherever this plan says `& $conda run -n transferx python` |
| A wheel fails to build | Confirm the interpreter is 64-bit 3.12; `asyncpg`, `psycopg2-binary`, `bcrypt` and `cryptography` all ship Windows wheels for it |
| Output shows `?` instead of `£` / `±` | Set `$env:PYTHONUTF8 = "1"` (do this in every session) |

Tip: `conda run` buffers output. For long runs use `& $conda run --no-capture-output -n transferx python ...`.

### A2. Prove the backend tests run

Tests use in-memory SQLite (`tests/conftest.py`: `sqlite+aiosqlite:///:memory:`). No database and no `.env` are needed.

```powershell
cd D:\Repo\transfer-x\backend
$env:PYTHONUTF8 = "1"
& $conda run --no-capture-output -n transferx python -m pytest -q tests/test_valuation_v2.py tests/test_last_fee.py tests/test_valuation.py
& $conda run --no-capture-output -n transferx python -m pytest -q        # whole suite; takes a while
```

Record the full-suite result **before changing any code**. If anything fails, write the failing test names into your working notes as the pre-existing baseline; they are not yours to fix.

### A3. Prove the frontend checks run

```powershell
cd D:\Repo\transfer-x\frontend
npm ci
npx tsc -b
npx vitest run
```

### A4. Read-only access to production data

Needed only for the backtest (B6) and the outcome report (B7). The user supplies the Railway Postgres **public** URL (Railway dashboard → Postgres service → Variables → `DATABASE_PUBLIC_URL`).

```powershell
$env:DATABASE_URL  = "<paste the URL here — never write it into a file, a commit or a log>"
$env:JWT_SECRET_KEY = "local-read-only-not-a-real-secret-0123456789abcdef"
$env:PYTHONUTF8    = "1"
cd D:\Repo\transfer-x\backend
& $conda run --no-capture-output -n transferx python -m scripts.valuation_backtest
```

`app/config.py` rewrites `postgres://` / `postgresql://` to `postgresql+asyncpg://` itself.

**Hard rules while `DATABASE_URL` points at Railway:**

- Run only `scripts.valuation_backtest` and `scripts.valuation_outcome_report`. Both are read-only.
- Never run `alembic`, `app.jobs.daily_refresh`, `scripts/recompute_valuations_railway.py`, or any `seed_*` / `backfill_*` / `onboard_*` / `repair_*` script.
- Never run `pytest` with it set (tests use their own SQLite engine, but don't take the risk).
- When done: `Remove-Item Env:DATABASE_URL`.

### A5. Record the baseline

Save the backtest output from A4 (overall line and the `fee <£5m`, `fee £5-25m`, `fee £25m+` lines). Phase B must not change the `v1`, `v2_intrinsic` or `v2_market` columns at all — if they move, something unintended changed.

### A6. (Optional) seeing the UI locally

Not required for acceptance; the frontend is verified by type-check and tests. The full app needs Docker Desktop (`docker compose up --build`, per `README.md`) and a synced database. Skip unless the user asks.

---

## 6. Phase B — The fee anchor (`market-v3`)

### B0. The rule in one paragraph

Take the player's last permanent fee. Restate it in today's money. Adjust it for what has changed since: he is older, his contract has run down, he is playing better or worse, he is more or less available, he may be in a different league. That gives an *anchor value*. Then move the model's number toward the anchor value by a *weight* between 0 and 1 that reflects how much the fee can still be trusted (who reported it, how old it is, how much he had played when it was paid). Bound the movement. Show it as a driver. If the fee cannot be trusted enough, do nothing and say why.

```text
fee_today    = fee_gbp × (1 + FEE_INFLATION_PER_YEAR) ^ years_since
anchor_value = fee_today × age_ratio × perf_ratio × league_ratio × contract_factor_now × availability_factor_now
weight       = source_credibility × basis_weight × recency_weight × evidence_weight
factor       = exp( clamp( weight × ln(anchor_value / value_before), ln 0.70, ln 1.60 ) )
fair_value   = value_before × factor            (then the release-clause cap, as today)
```

Assumptions (state them in the docs): at the time of the transfer the player had a fresh contract (contract factor 1.0) and was fit (availability factor 1.0), because neither is reconstructable from the data.

### B1. `backend/app/valuation/constants_v2.py`

Change line 14 to `MODEL_VERSION_V2 = "market-v3"` (keep the constant's name — fewer call sites to touch). Update the module docstring's first lines to mention `market-v3` adds Stage G2. Append:

```python
# ── Stage G2: last-fee anchor (market-v3) ─────────────────────────────────────
# A player's own last permanent fee, restated to today and adjusted for what has
# changed since, pulls the model toward it in proportion to how informative the
# fee still is. Bounded, visible as a driver, and skipped (with a reason) when
# the fee is weak evidence. Spec: docs/feature_spec/valuation/market-data.md.

# How far to trust the figure, by who says so.
FEE_ANCHOR_SOURCE_CREDIBILITY: dict[str, float] = {
    "TRANSFERX": 1.00,  # completed TransferX deal: the verified agreed fee
    "MANUAL": 0.80,     # staff-entered, with a source noted
    "REPORTED": 0.65,   # API-Football: a reported figure
}
# A release clause is a contract term, not a market-clearing price.
FEE_ANCHOR_BASIS_WEIGHT: dict[str, float] = {"PERMANENT": 1.00, "RELEASE_CLAUSE": 0.40}
FEE_ANCHOR_RECENCY_YEARS = 3.0  # recency weight = 1 / (1 + years / this): 3y → 0.50
FEE_ANCHOR_FULL_EVIDENCE_MINUTES = 1800.0  # pre-move weighted minutes for full weight
FEE_ANCHOR_MIN_EVIDENCE_MINUTES = 450.0  # known but below this: paid for potential
FEE_ANCHOR_UNKNOWN_EVIDENCE_WEIGHT = 0.60  # no pre-move stats on record at all
FEE_ANCHOR_MIN_WEIGHT = 0.25  # below this the anchor is not applied
FEE_ANCHOR_FACTOR_BOUNDS = (0.70, 1.60)
FEE_ANCHOR_PERF_EXPONENT = 0.5  # square root: 60 → 70 gives ~×1.08, not ×1.17
FEE_ANCHOR_PERF_BOUNDS = (0.80, 1.60)
FEE_ANCHOR_LEAGUE_EXPONENT = 0.25  # small: the fee already reflects the buying league
FEE_ANCHOR_LEAGUE_BOUNDS = (0.90, 1.10)
# The fee described a different player: young, a while ago, much better since.
FEE_ANCHOR_OUTGROWN_MAX_AGE = 24
FEE_ANCHOR_OUTGROWN_MIN_YEARS = 2.0
FEE_ANCHOR_OUTGROWN_MIN_SCORE_GAIN = 15.0
```

### B2. `backend/app/valuation/inputs_v2.py`

Add (above `FeatureSetV2`):

```python
@dataclass
class LastFee:
    """The player's own last permanent fee, with what the model knew about him
    at the time — the input to the market-v3 fee anchor."""

    fee_gbp: float
    transfer_date: str  # ISO date
    years_since: float  # unrounded, so a stored row replays exactly
    source: str  # "TRANSFERX" | "MANUAL" | "REPORTED"
    basis: str = "PERMANENT"  # | "RELEASE_CLAUSE"
    age_at_transfer: int | None = None
    score_at_transfer: float | None = None  # shrunk score from pre-move seasons
    minutes_at_transfer: float | None = None  # weighted minutes behind that score
    league_coefficient_at_transfer: float | None = None
    fee_display: str | None = None
    from_team: str | None = None
    to_team: str | None = None
```

In `FeatureSetV2` add the field `last_fee: LastFee | None = None` (after `games_available_total`).

In `features_from_snapshot`, pass `last_fee=LastFee(**snapshot["last_fee"]) if snapshot.get("last_fee") else None`.

### B3. `backend/app/valuation/engine_v2.py`

Import the new constants and `LastFee`. Add after the market-rate section:

```python
# ── Stage G2: last-fee anchor ─────────────────────────────────────────────────

@dataclass
class FeeAnchor:
    applied: bool
    factor: float  # 1.0 when not applied
    weight: float
    anchor_value: float | None  # the fee restated and adjusted to today
    fee_today: float | None  # the fee in today's money, before adjustments
    reason: str  # why it was applied, or why not

def _month_year(iso: str) -> str:
    return date.fromisoformat(iso).strftime("%b %Y")

def fee_anchor(
    last_fee: LastFee | None,
    *,
    position: str,
    age: int | None,
    score: float,
    coef: float,
    contract_f: float,
    availability_f: float,
    value_before: float,
) -> FeeAnchor:
    if last_fee is None or last_fee.fee_gbp <= 0 or value_before <= 0:
        return FeeAnchor(False, 1.0, 0.0, None, None, "No transfer fee on record")

    year = last_fee.transfer_date[:4]
    fee_today = last_fee.fee_gbp * (1 + FEE_INFLATION_PER_YEAR) ** last_fee.years_since

    minutes = last_fee.minutes_at_transfer
    if minutes is not None and minutes < FEE_ANCHOR_MIN_EVIDENCE_MINUTES:
        return FeeAnchor(False, 1.0, 0.0, None, fee_today,
                         f"The {year} fee was paid on too little playing time to anchor on")

    then = last_fee.score_at_transfer
    if (
        age is not None and age <= FEE_ANCHOR_OUTGROWN_MAX_AGE
        and last_fee.years_since >= FEE_ANCHOR_OUTGROWN_MIN_YEARS
        and then is not None and score - then >= FEE_ANCHOR_OUTGROWN_MIN_SCORE_GAIN
    ):
        return FeeAnchor(False, 1.0, 0.0, None, fee_today,
                         f"He has outgrown the fee paid in {year}")

    evidence = (
        FEE_ANCHOR_UNKNOWN_EVIDENCE_WEIGHT if minutes is None
        else min(1.0, minutes / FEE_ANCHOR_FULL_EVIDENCE_MINUTES)
    )
    weight = (
        FEE_ANCHOR_SOURCE_CREDIBILITY.get(last_fee.source, 0.0)
        * FEE_ANCHOR_BASIS_WEIGHT.get(last_fee.basis, 0.0)
        * (1.0 / (1.0 + last_fee.years_since / FEE_ANCHOR_RECENCY_YEARS))
        * evidence
    )

    age_then = last_fee.age_at_transfer
    age_ratio = (
        age_factor(position, age) / age_factor(position, age_then)
        if age is not None and age_then is not None else 1.0
    )
    perf_ratio = (
        clamp((score / then) ** FEE_ANCHOR_PERF_EXPONENT, *FEE_ANCHOR_PERF_BOUNDS)
        if then else 1.0
    )
    coef_then = last_fee.league_coefficient_at_transfer
    league_ratio = (
        clamp((coef / coef_then) ** FEE_ANCHOR_LEAGUE_EXPONENT, *FEE_ANCHOR_LEAGUE_BOUNDS)
        if coef_then and coef > 0 else 1.0
    )
    anchor_value = fee_today * age_ratio * perf_ratio * league_ratio * contract_f * availability_f

    if weight < FEE_ANCHOR_MIN_WEIGHT:
        return FeeAnchor(False, 1.0, weight, anchor_value, fee_today,
                         f"The {year} fee is too old or too weakly sourced to anchor on")

    lo, hi = FEE_ANCHOR_FACTOR_BOUNDS
    factor = math.exp(clamp(weight * math.log(anchor_value / value_before),
                            math.log(lo), math.log(hi)))
    return FeeAnchor(True, factor, weight, anchor_value, fee_today,
                     f"£{last_fee.fee_gbp / 1e6:.1f}m in {_month_year(last_fee.transfer_date)}"
                     f" is £{fee_today / 1e6:.1f}m in today's money; weight {weight:.2f}")
```

(`from datetime import date, datetime, timezone` — add `date` to the existing import. Reformat to the file's style; the logic above is the specification.)

Wire it into `compute_valuation_v2`:

1. Signature: add keyword-only `use_fee_anchor: bool = True`.
2. Immediately **after** the market-rate block (after the `if market.comps_used >= COMPS_MIN_COUNT: ... else: ...`) and **before** the "Confidence and band" block:

```python
    anchor = fee_anchor(
        fs.last_fee if use_fee_anchor else None,
        position=position, age=age, score=perf.score, coef=coef,
        contract_f=c_factor, availability_f=av_factor, value_before=value,
    )
    if anchor.applied:
        value = step("fee_anchor", "Last fee anchor", anchor.reason, anchor.factor, value)
    elif use_fee_anchor and fs.last_fee is not None:
        drivers.append(Driver("fee_anchor", "Last fee anchor", anchor.reason, 1.0, value))
```

3. Add `fee_anchor: FeeAnchor` to `ValuationOutcomeV2` and pass `fee_anchor=anchor` in the return. Because `ValuationOutcomeV2` has no defaults, add the field at the end and update the single constructor call.
4. The band, confidence and release-clause cap are untouched. The cap still applies last.
5. Update the module docstring formula to include `× fee_anchor`.

Replay stays exact with no extra plumbing: the anchor is a pure function of `fs.last_fee` (which stores `years_since` unrounded) and values already replayed.

### B4. `backend/app/players/last_fee.py`

Additive only:

- Add two keys to each row offered: `"source_key"` (`"REPORTED"` for `player_transfers` rows, `"TRANSFERX"` for deals) and `"basis"` (`"PERMANENT"`).
- The function will now be called with every player id in the batch job. Chunk the two `IN (...)` queries by 500 ids (asyncpg caps bind parameters at 32,767). Simplest: loop `for i in range(0, len(ids), 500)` around the existing body's queries.
- Existing keys, ordering and behaviour unchanged; `test_last_fee.py` must pass untouched. `LastTransfer(**row)` in `valuation/router.py` ignores unknown keys (pydantic default), and `lite/service.py` picks keys explicitly, so nothing else breaks.

### B5. `backend/app/valuation/features_v2.py`

Add:

```python
def build_last_fee(
    player: Player, fee: dict, stats_rows: list[PlayerStats], today: date
) -> LastFee | None:
    """A last_transfer_fees() row plus what the model knew of him at the time."""
    on = date.fromisoformat(fee["date"])
    position = player.position.value
    age_then = _age_at(player, on, today)
    seasons = build_seasons(
        str(player.id), position, age_then, stats_rows, up_to_season=reference_season(on)
    )
    score = minutes = coef = None
    if seasons:
        perf = engine_v2.performance_evidence(seasons)
        score, minutes = perf.score, perf.weighted_minutes
        coef = engine_v2.league_coefficient(seasons[0].league_id)
    return LastFee(
        fee_gbp=float(fee["fee_gbp"]),
        transfer_date=fee["date"],
        years_since=max((today - on).days / 365.25, 0.0),
        source=fee.get("source_key", "REPORTED"),
        basis=fee.get("basis") or "PERMANENT",
        age_at_transfer=age_then,
        score_at_transfer=score,
        minutes_at_transfer=minutes,
        league_coefficient_at_transfer=coef,
        fee_display=fee.get("fee_display"),
        from_team=fee.get("from"),
        to_team=fee.get("to"),
    )
```

Note on `minutes_at_transfer`: `performance_evidence` returns `weighted_minutes` = minutes × recency weights, and returns `0.0` when no season qualified. Treat `seasons == []` as *unknown* (`None`), and a real but small number as *known and small*.

Change `MarketFeatureProvider.get_features(self, db, player, last_fees: dict | None = None)`:

```python
        if last_fees is None:
            from app.players.last_fee import last_transfer_fees
            last_fees = await last_transfer_fees(db, [player.id])
        fee = last_fees.get(player.id)
        last_fee = build_last_fee(player, fee, list(rows), today) if fee else None
```

and pass `last_fee=last_fee` into the `FeatureSetV2(...)` it returns. Import inside the function as shown — `last_fee.py` already imports from `features_v2` lazily, so a top-level import would be circular.

Check the key type: `last_transfer_fees` keys are the `uuid.UUID` from the ORM rows. Use `uuid.UUID(str(player.id))` for the lookup, matching the rest of the file.

### B6. `backend/app/valuation/service.py` and `schemas.py`

`service.py`:

- `compute_and_store_valuation(db, player, comps=None, last_fees=None)`; pass `last_fees` to `_provider.get_features(db, player, last_fees)`.
- `compute_all_valuations`: after `comps = await build_comparables_index(db)` add `last_fees = await last_transfer_fees(db, [p.id for p in players])` and pass it on. Add `"fee_anchored": <count of rows whose inputs_json["fee_anchor"]["applied"]>` to the returned counts (the job run page shows this dict).
- `_serialize_features`: add `"last_fee": asdict(fs.last_fee) if fs.last_fee else None`.
- In the `PlayerValuation(...)` `inputs_json`: add `"fee_anchor": asdict(outcome.fee_anchor)`.
- `build_valuation_response`: `anchor = (row.inputs_json or {}).get("fee_anchor")` → `fee_anchor=FeeAnchorInfo(**anchor) if anchor else None`.
- Update the docstring that says "market-v2 valuation row".

`schemas.py`:

```python
class FeeAnchorInfo(BaseModel):
    """market-v3: how the player's own last fee moved the model, or why it didn't."""

    applied: bool
    factor: float
    weight: float
    anchor_value: float | None = None
    fee_today: float | None = None
    reason: str
```

Add to `ValuationResponse`: `fee_anchor: FeeAnchorInfo | None = None` with a comment "market-v3 only; null on earlier rows".

No change to `player_valuations` columns. **Phase B has no migration.**

### B7. Backtest — `backend/scripts/valuation_backtest.py`

Why a new column: the existing backtest predicts each fee from pre-transfer stats only, so it cannot tell whether anchoring helps. The honest test is **repeat transfers**: players sold for a fee more than once. Predict the *later* fee with and without anchoring on the *earlier* one.

1. `inputs_v2.CompRecord`: add `prev_fee: LastFee | None = None` (at the end; "kept for the backtest; not used by the engine").
2. `features_v2.build_comparables_index`: after the `events` list is built, load every fee-bearing permanent `PlayerTransfer` row for the players in `events` (no date limit — earlier fees are usually older than the 3-year window), parse with `app.players.last_fee.fee_gbp`. For each event, the previous fee is the newest such row dated more than 60 days before the event date. Build it with a small variant of `build_last_fee` where "today" is the event date:
   - `years_since = (event_date − prev_date).days / 365.25`
   - `age_at_transfer`, score, minutes, league coefficient from stats up to `reference_season(prev_date)`
   - `source="REPORTED"`.

   Refactor `build_last_fee` to accept `as_of: date` rather than duplicating it.
3. `backtest_rows`: add

```python
        anchor = engine_v2.fee_anchor(
            comp.prev_fee, position=comp.position, age=comp.age_at_transfer,
            score=comp.score_at_transfer, coef=comp.league_coefficient,
            contract_f=1.0, availability_f=1.0,
            value_before=comp.intrinsic_gbp * market.factor,
        )
```

   and row keys `"prev_fee_gbp"`, `"v3_anchor": v2_market × anchor.factor`, `"anchor_applied"`, `"anchor_reason"`.

   Caveat to print under the table: the comparison is in today's money for the actual fee and at-transfer money for the previous fee restated to the transfer date; inflation between the transfer and today scales both predictions equally, so the comparison between `v2_market` and `v3_anchor` is fair, but neither includes contract, form or availability at the time.

4. `run`: keep the existing table unchanged (still three models). Add a second table titled `Repeat transfers (players with an earlier fee)`, comparing `v2_market` and `v3_anchor` on rows where `prev_fee_gbp` is set: overall, and split into anchor applied / not applied. Then print counts of `anchor_reason` for skipped rows.
5. `--csv` picks up the new columns automatically (`fieldnames=list(rows[0])`). Open the CSV with `encoding="utf-8"`.

**Calibration rule.** Run on production.

- If the repeat-transfer set has fewer than about 15 rows: keep the defaults in B1, and say so in the report. Do not tune on noise.
- Otherwise, if `v3_anchor` is worse than `v2_market` on "within ±25%" or median bias: try `FEE_ANCHOR_SOURCE_CREDIBILITY["REPORTED"]` in {0.5, 0.65, 0.8, 0.9} × `FEE_ANCHOR_RECENCY_YEARS` in {2, 3, 4, 5}; pick the best by ±25% then by |bias|; report the whole grid to the user. Change nothing else.
- If no setting beats `v2_market`: stop and tell the user. Do not ship an anchor that makes the backtest worse.

### B8. Outcome report — new `backend/scripts/valuation_outcome_report.py`

Full specification in section 11. Build it in Phase B so it can run against production before any deploy.

### B9. Tests for Phase B — `backend/tests/test_valuation_v2.py`

Add a builder next to `_comp`:

```python
def _last_fee(fee=60_000_000.0, years=1.0, **overrides) -> LastFee:
    base = dict(fee_gbp=fee, transfer_date="2025-07-01", years_since=years, source="REPORTED",
                age_at_transfer=24, score_at_transfer=None, minutes_at_transfer=2700.0,
                league_coefficient_at_transfer=1.0)
    base.update(overrides)
    return LastFee(**base)
```

Pure engine tests (compare `compute_valuation_v2(_fs(last_fee=...))` with `compute_valuation_v2(_fs())`):

| Test | Asserts |
|---|---|
| `test_fee_above_model_raises_value_and_below_lowers_it` | direction of the move; a `fee_anchor` driver with factor ≠ 1 |
| `test_fee_anchor_factor_is_bounded` | absurd fees (£1bn, £100k) give exactly ×1.60 and ×0.70 |
| `test_fee_anchor_weight_falls_with_age_of_fee` | factor closer to 1 at 3 years than at 0.5 |
| `test_old_reported_fee_is_not_applied_and_says_why` | 6-year-old fee: value unchanged, neutral driver present, `outcome.fee_anchor.applied is False`, reason mentions the year |
| `test_source_credibility_orders_the_pull` | TRANSFERX moves more than MANUAL, which moves more than REPORTED |
| `test_release_clause_basis_weighs_less` | same fee, `basis="RELEASE_CLAUSE"`, smaller move (or skipped) |
| `test_fee_paid_on_little_playing_time_is_skipped` | `minutes_at_transfer=300` → not applied |
| `test_unknown_pre_move_stats_reduce_the_weight` | `minutes_at_transfer=None` → applied when recent, with weight × 0.6 |
| `test_outgrown_fee_is_skipped` | age 22, 3 years, `score_at_transfer` 15+ below current → not applied, reason "outgrown" |
| `test_expiring_contract_pulls_the_anchor_down` | same fee, `contract_years_remaining=0.5` vs `4.0`: lower `anchor_value` — the anchor is not "value = last fee" |
| `test_release_clause_still_caps_after_the_anchor` | fee anchor pushes above the clause → final value equals the clause |
| `test_no_fee_means_no_anchor_driver` | `_fs()` has no `fee_anchor` driver and equals the pre-change value |
| `test_use_fee_anchor_false_reproduces_v2` | `compute_valuation_v2(fs_with_fee, use_fee_anchor=False).fair_value == compute_valuation_v2(fs_without_fee).fair_value` |
| extend `test_drivers_rebuild_the_value` | product of driver factors × anchor == unrounded value, with a fee present |

Service / DB tests:

| Test | Asserts |
|---|---|
| `test_service_stores_and_serves_the_fee_anchor` | player with stats + a `PlayerTransfer("€ 60M", 1 year ago)`: stored `inputs_json["fee_anchor"]["applied"] is True`, `inputs_json["features"]["last_fee"]["source"] == "REPORTED"`, API `GET /valuation/players/{id}` returns `fee_anchor.applied` and a `fee_anchor` driver, `model_version == "market-v3"` |
| extend `test_v2_row_replays_exactly_from_inputs_json` | with a last fee present, `compute_valuation_v2(features_from_snapshot(...), market=MarketRate(**...))` reproduces `fair_value`, low and high exactly |
| `test_own_transfer_still_never_enters_market_rate` | the player's own fee is in the comps index but his `top_comps` never contain his own `player_id` |
| `test_last_fee_context_uses_pre_move_seasons_only` | stats in 2023 and 2025, transfer July 2024 → `score_at_transfer` comes from the 2023 season only |
| extend `test_backtest_rows_predict_each_model_leave_one_out` | `v3_anchor == v2_market` with no `prev_fee`; differs with one |

Version-string updates: `backend/tests/test_valuation.py:348` (`"market-v2"` → `"market-v3"`). Other tests with hard-coded values (for example `test_sales.py`, "market-v2: £154.4m") must **not** change, because their fixtures have no transfer fee. If one moves, find out why before editing it.

### B10. Phase B gate

1. Full backend suite green (or only the A2 baseline failures).
2. `ruff check app scripts tests` clean on touched files.
3. Backtest on production: the three original columns identical to the A5 baseline; the repeat-transfer table produced; calibration rule applied.
4. Outcome report produced on production and shown to the user.
5. **Stop here and get the user's reaction to the report before Phase C.**

---

## 7. Phase C — Staff-entered fees

### C1. Migration `backend/migrations/versions/0111_manual_transfer_fees.py`

Read `docs/engineering/database-migrations.md` and copy the header style of `0110_conversation_reads.py` (`down_revision` must be 0110's revision id — open the file to get the exact string).

Additive, nullable, safe to deploy ahead of the code:

```python
def upgrade() -> None:
    op.add_column("player_transfers", sa.Column("fee_basis", sa.String(20), nullable=True))
    op.add_column("player_transfers", sa.Column("source_note", sa.String(500), nullable=True))
    op.add_column("player_transfers", sa.Column("source_url", sa.String(512), nullable=True))
    op.add_column("player_transfers", sa.Column("entered_by_user_id", sa.Uuid(), nullable=True))
    op.create_foreign_key("fk_player_transfers_entered_by", "player_transfers", "users",
                          ["entered_by_user_id"], ["id"], ondelete="SET NULL")

def downgrade() -> None:  # reverse order
```

SQLite (tests build the schema from the models, not from migrations) is unaffected. Mirror the four columns on `PlayerTransfer` in `backend/app/players/models.py`, and update its docstring: "Transfer history: cached from API-Football, plus staff-entered rows (`vendor = 'manual'`)".

Conventions for a manual row: `vendor="manual"`, `transfer_type="Transfer"`, `fee_basis` in {`"PERMANENT"`, `"RELEASE_CLAUSE"`}, `source_note` required, `fetched_at` = now.

### C2. Stop the vendor sync deleting manual rows

`backend/app/vendor/history.py:104`:

```python
    await db.execute(delete(PlayerTransfer).where(
        PlayerTransfer.player_id == player.id, PlayerTransfer.vendor == VENDOR))
```

Then read `GET /players/market/{player_id}/transfers` in `backend/app/players/router.py` (~line 445). It auto-refreshes when the cache is older than 24h. Make sure its freshness check and any delete there consider **vendor rows only** — otherwise a just-added manual row makes the cache look fresh and suppresses the vendor refresh, or gets deleted. Also search for any other `delete(PlayerTransfer)`:

```powershell
# from repo root
rg "delete\(PlayerTransfer" backend
```

Test (`backend/tests/test_admin_transfer_fees.py`): a manual row survives `refresh_transfers` called with a stub client returning one vendor transfer.

### C3. Manual rows win where they should

`backend/app/players/last_fee.py`:

- For `t.vendor == "manual"`: `source: "Manual"`, `source_key: "MANUAL"`, `basis: t.fee_basis or "PERMANENT"`, `source_note: t.source_note`.
- Same-move rule: if a manual row and a vendor row for the same player are dated within 60 days of each other, drop the vendor row (the manual row is a correction). Implement by collecting the player's manual dates first, then skipping vendor rows within 60 days of any of them. Otherwise "newest date wins", as today. A later TransferX deal still wins by date.
- Add a test for each rule in `test_last_fee.py`.

`backend/app/valuation/features_v2.py::build_comparables_index`:

- Skip a vendor-reported row when a manual row exists for that player within 60 days (same pattern as the existing `platform_moves` check).
- Manual rows enter the index as `source="REPORTED"` (no new comps weight).
- Skip rows with `fee_basis == "RELEASE_CLAUSE"` as comparables.

`backend/app/valuation/schemas.py::LastTransfer`: add `source_note: str | None = None` and `basis: str | None = None`; update the `source` comment to include `"Manual"`.

### C4. Admin API — `backend/app/admin/router.py` (+ schemas in the admin schemas module)

All three use `Depends(get_current_superuser)`. Follow `update_player` (line 678) for structure, error handling and commit/rollback.

**`GET /admin/players/{player_id}/transfer-fees`** → list of
`{id, transfer_date, transfer_type, from_club, to_club, fee_display, fee_gbp, vendor, fee_basis, source_note, source_url, entered_by_user_id}`, newest first, all vendors. `fee_gbp` via `last_fee.fee_gbp(fee_display)`.

**`POST /admin/players/{player_id}/transfer-fees`** — body:

| Field | Rule |
|---|---|
| `amount` | number, > 0, ≤ 500,000,000 |
| `currency` | `"GBP"` \| `"EUR"` \| `"USD"` |
| `transfer_date` | date, not in the future |
| `from_club`, `to_club` | strings, 1–200 chars |
| `basis` | `"PERMANENT"` (default) \| `"RELEASE_CLAUSE"` |
| `source_note` | required, 5–500 chars — where the figure comes from ("Club statement 14 Jul 2023", "BBC Sport") |
| `source_url` | optional, ≤ 512 chars, must start with `http://` or `https://` |

Behaviour:

1. 404 if the player does not exist.
2. Build `fee_display` in the vendor's shape so both existing parsers read it back: symbol + space + compact amount — `"£ 105M"`, `"€ 4.5M"`, `"€ 750K"`, `"$ 12M"`. Helper:

```python
def format_fee_display(amount: float, currency: str) -> str:
    symbol = {"GBP": "£", "EUR": "€", "USD": "$"}[currency]
    if amount >= 1_000_000:
        return f"{symbol} {amount / 1_000_000:g}M"
    return f"{symbol} {amount / 1_000:g}K"
```

   Put it in `players/last_fee.py` beside `fee_gbp` and test the round trip (`fee_gbp(format_fee_display(x, cur))` ≈ x converted) for £/€/$ at 750k, 4.5m, 105m.
3. Insert the `PlayerTransfer` (`vendor="manual"`, `entered_by_user_id=current_user.id`).
4. `admin_audit.record(db, current_user, "player.transfer_fee_added", entity_type="player", entity_id=player.id, description=f"Recorded a transfer fee for {player.name}", details={amount, currency, transfer_date, from, to, basis, source_note, source_url})`.
5. Recompute that player so the anchor shows at once: `await valuation_service.compute_and_store_valuation(db, player)` (returns `None` for an ineligible player — fine).
6. Commit. Return the created row (201).

**`DELETE /admin/players/{player_id}/transfer-fees/{transfer_id}`** — 404 if not found or not this player's; 400 if `vendor != "manual"` ("Only staff-entered fees can be removed"). Audit `player.transfer_fee_removed` with the deleted values, recompute, commit, 204.

### C5. Tests — new `backend/tests/test_admin_transfer_fees.py`

Use the registration/auth helpers from `tests/conftest.py` and look at an existing admin test for how a superuser is created.

- non-superuser → 403 on all three endpoints;
- missing or too-short `source_note` → 422; future date → 422; bad currency → 422;
- after POST: `GET /valuation/players/{id}` and the ledger show `last_transfer.source == "Manual"` with the note; `fee_gbp` matches the conversion;
- a manual row within 60 days of a vendor row replaces it as the last transfer; a manual row for an older move does not beat a newer vendor fee;
- with stats present, the stored valuation's `inputs_json["features"]["last_fee"]["source"] == "MANUAL"` and the weight reflects credibility 0.80;
- `basis="RELEASE_CLAUSE"` is stored and reaches `LastFee.basis`;
- DELETE restores the vendor fee as the last transfer; DELETE on a vendor row → 400;
- one audit row per add and per delete;
- the manual row survives `refresh_transfers` (C2).

### C6. Phase C gate

Full backend suite green. Remember: from here until migration `0111` is deployed to Railway, the read-only scripts cannot run against production (the ORM selects columns that do not exist there yet).

---

## 8. Phase D — Frontend, docs, rollout

### D1. Frontend

Read `docs/design-system/RULES.md` first. Reuse existing components and tokens; no new colours or one-off styles.

| File | Change |
|---|---|
| `frontend/src/types/api.ts` | Add `FeeAnchorInfo { applied: boolean; factor: number; weight: number; anchor_value: number \| null; fee_today: number \| null; reason: string }`. Add `fee_anchor?: FeeAnchorInfo \| null` to `FairValueSignal` (near line 567). Add `source_note?: string \| null; basis?: string \| null` to `LastTransfer`. Update the "market-v2" comments at lines 525 and 568 |
| `components/players/ValuationBreakdownPopover.tsx` | The applied anchor renders automatically as a `DriverRows` line ("Last fee anchor ×1.16 £52.1m", detail in the `title`). Add one muted line under the build-up when `signal.fee_anchor && !signal.fee_anchor.applied && signal.last_transfer`: `Last fee not used: {reason}`. Update the header comment. **Never remove the footer disclaimer** |
| `components/players/ledger/FactsStrip.tsx` | "Last transfer" cell sub-line: append the source — `· API-Football`, `· TransferX`, or `· Manual`; put `source_note` in the cell's `title` when present |
| `pages/admin/AdminPlayerDetailPage.tsx` | A "Transfer fees" card: table (date, from → to, fee, source, note, delete button on manual rows only) and an add form (amount, currency, date, from, to, basis, source note, source URL). Follow this page's existing data-fetching and form patterns (look at how it calls `PATCH /admin/players/{id}`); on success invalidate the player's valuation and ledger queries |
| Tests | `ValuationBreakdownPopover.test.tsx`: update the `model_version` fixture; add "shows the last fee anchor step" and "says why the last fee was not used". `FactsStrip.test.tsx`: source shown. A test for the admin card: lists rows, submits, delete only on manual rows |

Copy: "Last fee anchor", "Last transfer", "last reported fee", "TransferX model". Never "true value", "real value", "overpriced", "bargain".

```powershell
cd D:\Repo\transfer-x\frontend; npx tsc -b; npx vitest run
```

### D2. Documentation (invoke the `documentation-standards` skill, then `session-lifecycle`)

| File | Change |
|---|---|
| `docs/feature_spec/valuation/market-data.md` | Front-matter `status` → "Phase 1 implemented (simplified) {date}; Phases 2–4 not built". Add a section "What was built, and how it differs from this spec": no `transfer_fee_observations` table or canonical fee columns (manual rows in `player_transfers` instead); contract and availability at the transfer assumed neutral; unknown pre-move stats use an evidence weight of 0.60; outgrown-fee rule thresholds; no feature flag; PlayerElo is the next step |
| `docs/feature_spec/valuation/model.md` | Add Stage G2 to the stage table and the formula; a `market-v3` note; the new backtest tables with their sample sizes |
| `docs/CHANGELOG.md`, `docs/IMPLEMENTATION_STATUS.md` | Entries for `market-v3`, staff-entered fees, the sync fix |
| `docs/engineering/api-reference.md` | The three admin endpoints; `fee_anchor` on the valuation responses; `source_note`/`basis` on `last_transfer` |
| `docs/architecture/data-model.md` | Four new `player_transfers` columns; `vendor = 'manual'` |
| `docs/business/glossary.md` | "Last fee anchor" |
| `docs/SESSION_HANDOVER.md` | Session summary, what is left, how to run the report |

### D3. Rollout

1. Merge → Railway deploys → migration `0111` applies on start.
2. New `market-v3` rows are written by the next daily recompute. Old rows stay (append-only), so the UI shows `market-v3` once each player has a newer row.
3. To see them sooner, `scripts/recompute_valuations_railway.py` recomputes everything. **That is a write to production: run it only when the user explicitly asks.**
4. After the recompute, re-run the outcome report against production and confirm it matches the pre-deploy report.

---

## 9. Follow-ups (not in this plan)

1. **PlayerElo pilot**, admin-only shadow mode, through the existing `backend/app/enrichment/` adapter seam (`ValuationProvider` protocol, registry). Before building: confirm in writing that the licence covers display to club users, storage and derived metrics. Store provider values in their own table; never write them into `fair_value`.
2. Re-run the backtest and calibration after the January 2027 window.
3. Full `transfer_fee_observations` audit model, once a second fee source exists.
4. A "valuation stack" card (model / market / last fee side by side) once a market feed exists.

---

## 10. Acceptance checklist

| # | Check | How | Pass when |
|---|---|---|---|
| 1 | Backend suite | `python -m pytest -q` in `backend/` | Green, or only the A2 baseline failures |
| 2 | Lint | `python -m ruff check app scripts tests` | No new findings in touched files |
| 3 | Frontend | `npx tsc -b; npx vitest run` | Green |
| 4 | Replay | extended replay test | A stored `market-v3` row reproduces exactly from `inputs_json` |
| 5 | No regression without a fee | `test_use_fee_anchor_false_reproduces_v2`, untouched hard-coded values in other tests | Players without a fee are valued exactly as before |
| 6 | Backtest, production, read-only | `python -m scripts.valuation_backtest --csv <scratch>\backtest.csv` | Original three columns equal the A5 baseline; on repeat transfers `v3_anchor` is no worse than `v2_market` on ±25% and \|bias\|; sample size printed |
| 7 | Bounds | outcome report + CSV | No anchor factor outside 0.70–1.60 anywhere |
| 8 | Outcome report | section 11 | Every named player has a before/after pair with a reason, or an explicit empty state. No invented numbers |
| 9 | Manual fee end to end | `test_admin_transfer_fees.py` | Add → shown as last transfer with source → value moves → survives vendor refresh → delete restores |
| 10 | Audit | same test file | One audit row per add/delete, with who and what |
| 11 | Permissions | existing valuation permission tests | Player accounts still 403; private players 404; admin endpoints superuser-only |
| 12 | Copy | review the diff | None of "true value", "real value", "overpriced", "bargain" |
| 13 | Docs | D2 | All listed files updated |

---

## 11. The user-facing outcome test

### 11.1 What it is

A read-only script that prints, for named players, the value **before** this change (`market-v2`) and **after** it (`market-v3`), next to the real last fee, with the reason in plain English. This is what the product owner looks at to judge quality.

### 11.2 Script — `backend/scripts/valuation_outcome_report.py`

```powershell
cd D:\Repo\transfer-x\backend
& $conda run --no-capture-output -n transferx python -m scripts.valuation_outcome_report `
    --players "Haaland,Ronaldo,Rice,Palmer,Yamal,Bellingham,Saka" `
    --also 6 `
    --out D:\Repo\transfer-x\valuation_outcome_report.md
```

Requirements:

- **Read-only.** Model it on `valuation_backtest.py`: `import app.main` to register models, `AsyncSessionLocal()`. If `db.bind.dialect.name == "postgresql"`, execute `SET TRANSACTION READ ONLY` first. Never `add`, `flush` or `commit`. Compute in memory with `MarketFeatureProvider().get_features` and `engine_v2.compute_valuation_v2`; do **not** call `compute_and_store_valuation`.
- **Arguments:** `--players` (comma-separated name fragments), `--also N` (default 6), `--out PATH` (Markdown, UTF-8), `--summary-only`.
- **Name matching:** case-insensitive substring on `Player.name` (API-Football stores names like "E. Haaland" and "Cristiano Ronaldo"). When several players match, take the one with the most minutes in his latest season and list the others under "also matched". When none match: "Not in the database".
- **Lesser-known picks (`--also`):** deterministic, no randomness. Candidates: eligible players with a last fee, at least 1,800 minutes in the latest season, and either a `market-v2` value under £15m or a league coefficient ≤ 0.40. Sort by `str(player.id)`. Take half with the anchor applied and half with it skipped, so both behaviours appear.
- **Per player:** build features once, load `comps` once for the whole run, then
  - `before = compute_valuation_v2(fs, comps, use_fee_anchor=False)`
  - `after  = compute_valuation_v2(fs, comps)`
- **Empty states — never a made-up number:**
  - "Not in the database"
  - "No valuation: no stats on record" / "No valuation: under {MIN_MINUTES} minutes this season"
  - "No fee on record — value unchanged"
  - "Last fee not used: {reason}"

### 11.3 Output format

Console and Markdown, one block per player:

```text
Declan Rice · 27 · MID · Arsenal (Premier League)
  Last transfer      £99.7m · Jul 2023 · West Ham → Arsenal · source: API-Football
  Before (market-v2) £45.0m
  After  (market-v3) £52.1m      range £44.3m – £59.9m      change +16%
  Why                Last fee anchor ×1.16. £99.7m in Jul 2023 is £121m in today's money;
                     a 3.3-year-old reported fee carries weight 0.31.
  Gap to last fee    before −55%  →  after −48%
```

(The numbers above are illustrative. The script prints real ones.)

Then a summary table of all named and picked players:

| Player | Age | Club | Last fee | Before | After | Change | Anchor |
|---|---|---|---|---|---|---|---|

Then **totals across every eligible player** in the database:

- players valued; with a last fee; anchor applied; skipped, by reason;
- median change where applied; share moved by more than 10%; largest rise and fall (names and numbers);
- the repeat-transfer backtest table from B7, with its sample size.

Then a fixed footer:

> Model estimate — not an official valuation. The last fee is a reported figure unless marked TransferX or Manual. The anchor is bounded to ×0.70–×1.60 and weighted by the age and source of the fee.

### 11.4 What to expect, so nobody is surprised

| Player | Likely outcome | Why |
|---|---|---|
| **Declan Rice** | Moves up toward his fee, by tens of percent, not to £100m | Fee from July 2023 is 3.3 years old and reported, so its weight is about 0.3; the factor is capped at ×1.60 |
| **Cole Palmer** | Probably "outgrown the fee paid in 2023" — anchor not used | Young, fee over two years old, far better since. Using £40m would drag him *down* |
| **Erling Haaland** | Probably "too old or too weakly sourced" — anchor not used | The 2022 fee was a release clause, paid on Bundesliga stats from before our data starts. Staff can record it as a manual `RELEASE_CLAUSE` row |
| **Cristiano Ronaldo** | No fee to anchor (free transfer to Al-Nassr, Jan 2023); may have no valuation at all | Only valued if the Saudi league is among the synced competitions |
| **Lamine Yamal** | No fee on record — value unchanged | Academy graduate. Only a licensed market feed helps here (follow-up 1) |
| **Lesser-known players with a recent fee** | The clearest improvement | A one-year-old fee carries weight around 0.5, so the model moves about half-way (in log terms) toward the adjusted fee |

If the report contradicts this table, that is information, not a failure: report what the data shows.

### 11.5 How the user judges it

Ask the user to read the report and answer three questions:

1. For players with a recent fee, is the "After" number more believable than "Before"?
2. Is every reason understandable without knowing the model?
3. Is there any player where the anchor made the number *less* believable? (Name them — those cases drive the calibration in B7.)

Offer to publish the Markdown report as a shareable page once it exists.

---

## 12. Risks the implementer must not paper over

| Risk | What to do |
|---|---|
| **Small samples.** About 84 fee-bearing comparables in production in October; the repeat-transfer set is smaller | Print n beside every percentage. Do not tune on fewer than ~15 rows |
| **Stats coverage starts around 2022** | Older fees get the reduced unknown-evidence weight and are often skipped. Intended; say so in the report |
| **Vendor fees are reported, not verified; release clauses are not flagged** | Manual rows with `basis="RELEASE_CLAUSE"` are the correction path |
| **The anchor could overfit the last fee** | Bounds, weights, the outgrown rule, the backtest gate in B7 |
| **Production is live** | Read-only scripts only. No migrations, refreshes or recomputes against Railway without the user's explicit request |
| **A hard-coded test value changes unexpectedly** | Means a fixture has a transfer fee you did not expect, or the no-fee path changed. Investigate; do not just update the number |
| **`conversation.jfif` was not read** (2.4 MB, over the tool's limit) | This plan rests on the summary in `docs/feature_spec/valuation/brief.md`. If the image says something that summary does not, the user should flag it |

---

## Appendix A — File map

| Path | Phase | Change |
|---|---|---|
| `backend/app/valuation/constants_v2.py` | B | version → `market-v3`; `FEE_ANCHOR_*` |
| `backend/app/valuation/inputs_v2.py` | B | `LastFee`; `FeatureSetV2.last_fee`; `CompRecord.prev_fee`; snapshot rebuild |
| `backend/app/valuation/engine_v2.py` | B | `FeeAnchor`, `fee_anchor()`, wiring, `use_fee_anchor` |
| `backend/app/valuation/features_v2.py` | B, C | `build_last_fee`; provider accepts `last_fees`; `prev_fee` in the comps index; manual rows in the comps index |
| `backend/app/valuation/service.py` | B | pass `last_fees`; serialise `last_fee` and `fee_anchor`; response field |
| `backend/app/valuation/schemas.py` | B, C | `FeeAnchorInfo`; `LastTransfer.source_note`, `.basis` |
| `backend/app/players/last_fee.py` | B, C | `source_key`, `basis`, chunking; manual rows; `format_fee_display` |
| `backend/scripts/valuation_backtest.py` | B | repeat-transfer table |
| `backend/scripts/valuation_outcome_report.py` | B | **new** |
| `backend/migrations/versions/0111_manual_transfer_fees.py` | C | **new** |
| `backend/app/players/models.py` | C | four columns on `PlayerTransfer` |
| `backend/app/vendor/history.py` | C | delete vendor rows only |
| `backend/app/players/router.py` | C | freshness check on vendor rows only |
| `backend/app/admin/router.py` (+ admin schemas) | C | three endpoints |
| `backend/tests/test_valuation_v2.py`, `test_valuation.py`, `test_last_fee.py` | B, C | new and updated tests |
| `backend/tests/test_admin_transfer_fees.py` | C | **new** |
| `frontend/src/types/api.ts` | D | types |
| `frontend/src/components/players/ValuationBreakdownPopover.tsx` (+ test) | D | "not used" line |
| `frontend/src/components/players/ledger/FactsStrip.tsx` (+ test) | D | source |
| `frontend/src/pages/admin/AdminPlayerDetailPage.tsx` (+ test) | D | "Transfer fees" card |
| `docs/...` | D | see D2 |

## Appendix B — Worked example (for a unit test and for intuition)

Midfielder, 27, Premier League, contract 1.6 years left, fully available. Last fee £100m, 3.3 years ago, reported, pre-move stats on record (2,700 weighted minutes, score 62 then, 70 now). Model before the anchor: £45m.

```text
fee_today    = 100 × 1.06^3.3                  = £121.2m
age_ratio    = 1.00 / 1.00                     = 1.00     (27 is inside the MID peak window)
perf_ratio   = (70 / 62)^0.5                   = 1.063
league_ratio = 1.00
contract     = 0.70 + (0.88 − 0.70) × 0.6      = 0.808    (CONTRACT_KNOTS: 1y → 0.70, 2y → 0.88)
availability = 1.00
anchor_value = 121.2 × 1.063 × 0.808           = £104.1m
weight       = 0.65 × 1.00 × 1/(1 + 3.3/3) × 1 = 0.310
factor       = exp(0.310 × ln(104.1 / 45))     = exp(0.310 × 0.839) = 1.297
fair_value   = 45 × 1.297                      = £58.4m
```

So a £45m model value becomes about £58m: clearly pulled toward the fee, clearly not the fee. With a one-year-old fee the weight would be 0.49 and the result about £67m. Verify these figures against the real constants when writing the test; do not paste them in blind.

## Appendix C — Command reference

```powershell
$conda = "C:\Aaron\Tools\Anaconda38\condabin\conda.bat"
$env:PYTHONUTF8 = "1"
cd D:\Repo\transfer-x\backend

# tests
& $conda run --no-capture-output -n transferx python -m pytest -q
& $conda run --no-capture-output -n transferx python -m pytest -q tests/test_valuation_v2.py -k fee_anchor
& $conda run --no-capture-output -n transferx python -m ruff check app scripts tests

# read-only production runs (set DATABASE_URL and JWT_SECRET_KEY first — section A4)
& $conda run --no-capture-output -n transferx python -m scripts.valuation_backtest --csv $env:TEMP\backtest.csv
& $conda run --no-capture-output -n transferx python -m scripts.valuation_outcome_report --players "Haaland,Ronaldo,Rice,Palmer,Yamal" --also 6 --out D:\Repo\transfer-x\valuation_outcome_report.md
Remove-Item Env:DATABASE_URL

# frontend
cd D:\Repo\transfer-x\frontend; npx tsc -b; npx vitest run
```

---

## Addendum 1 — Review of the first execution, and the revised plan (2026-11-11 10:14)

Written after reviewing `docs/feature_spec/valuation/execution-log.md` and the uncommitted diff on branch `valuation-v3-fee-anchor`. **Where this addendum disagrees with sections 1–12 or with the log, this addendum wins.** Everything not mentioned here stands.

### R0. What the review found

Checked on 2026-11-11: the diff matches Phases B, C and D of the plan; `pytest tests/test_admin_transfer_fees.py tests/test_last_fee.py tests/test_valuation_v2.py tests/test_valuation.py` gives 119 passed; the engine code is the B3 specification; the migration, the sync fix, the cache-freshness fix and the admin endpoints are as specified.

What is wrong or missing:

| # | Finding | Severity |
|---|---|---|
| 1 | **The Phase B gate was skipped.** Phases C and D were built without the production backtest or the outcome report (B10.3–B10.5). The model is unproven: no constant has been checked against a single real fee | Blocking |
| 2 | **The log's §8 "how to finish" commands cannot work.** `PlayerTransfer` now maps four columns that production does not have, so every `select(PlayerTransfer)` in both read-only scripts fails with `UndefinedColumnError` until migration `0111` is deployed. Section 4 of this plan warned about exactly this | Blocking |
| 3 | **A stale fee can anchor a player who has since left on a free.** "Newest move with a known fee" ignores later free transfers, so a £30m fee from 2022 still pulls a player who was released in 2025 | Model defect — fix before the production run |
| 4 | The skip reason "too old or too weakly sourced" is also given to a *recent* fee skipped for thin playing time or a release-clause basis, where it is false | Copy defect — fix before any `market-v3` row is stored |
| 5 | The calibration rule (B7) counts all repeat transfers, but most will have the anchor skipped (earlier fees are usually old, with no pre-move stats). The sample that matters is "anchor applied" | Plan defect |
| 6 | The calibration grid has no tooling: 16 settings would mean 16 edits of the constants and 16 full runs against production | Plan gap |
| 7 | The outcome report shows one largest rise and one largest fall. The owner's third question ("where did the anchor make it worse?") needs the list, especially the falls | Report gap |
| 8 | Name matching is a bare substring: "Rice" matches Price, Brice, Maurice; "Saka" matches Sakamoto. The pick is "most minutes", which is usually right but not by design | Report gap |
| 9 | `source_note` is returned by the public ledger endpoint and shown in the "Last transfer" tooltip to every viewer, including signed-out viewers of a PUBLIC player. Staff are not told the note is public | Product / confidentiality |
| 10 | "Remove" on a staff fee deletes at once, with no confirmation, although it writes an audit row and revalues the player | UX |
| 11 | The Appendix B worked example has no test. No test shows `engine_v2.parse_fee` (the comparables parser) reads a `format_fee_display` string | Test gap |
| 12 | A2 was wrong: the tests do need `JWT_SECRET_KEY` in the environment (any non-default string), or `app.config` refuses to import | Plan error |
| 13 | A2's baseline was never captured before the code changed. The one backend failure (`test_real_world.py::test_playing_on_for_the_old_club_is_for_staff_and_cant_be_applied`) is credible as pre-existing: `real_world.py:349` uses `strftime("%-d …")`, which Windows rejects, and the file is untouched | Accept; do not fix here |
| 14 | The log's commands write `backtest.csv` and the report into the repo root | Hygiene |

Not defects, recorded so nobody "fixes" them: the admin endpoints' `except Exception → 400` copies the house pattern in `update_player`; the full-repo `ruff` output is pre-existing noise (rules beyond the project's config); the non-applied anchor is stored as a ×1.00 driver, which the popover hides by design.

### R1. Order of work from here

1. R2 (environment corrections) — nothing to build.
2. R3, R4, R5, R6, R7 — code and tests, all local. These change what the production run prints, so they come first.
3. R8 — the production run and the gate. **Needs the user** (a `DATABASE_URL`, and a choice between two routes).
4. R9 — small frontend items.
5. R10 — docs and log.

Do not commit, deploy, or run anything against Railway except as R8 says.

### R2. Environment corrections

- Tests: set `$env:JWT_SECRET_KEY = "local-test-only-not-a-real-secret-0123456789abcdef"` and `$env:PYTHONUTF8 = "1"` before `pytest`. No database is needed.
- Baseline: treat the Windows-only `strftime` failure in R0 #13 as the known baseline. If you want proof, `git stash -u`, run that one test, `git stash pop` — only with the user's agreement, since the whole work is uncommitted.
- Script outputs go to the scratch or temp directory (`$env:TEMP\backtest.csv`, `$env:TEMP\valuation_outcome_report.md`), never the repo root.

### R3. Do not anchor on a fee the player has since moved on from

**Rule.** If the player has a later *permanent free* move after the fee, the fee is not used: `FeeAnchor(applied=False, …, reason="He has moved on a free transfer since the {year} fee")`.

**Why only free moves.** `vendor/history.py` stores `fee_display = None` for both `"N/A"` (undisclosed) and loans, and loan returns arrive as non-loan rows with text like "Back from Loan". An explicit `"Free"` is the only later move that reliably says the old fee no longer describes his market. Do not guess from club names — they differ between sources.

**Implementation.**

- `players/last_fee.py`: the `PlayerTransfer` query already loads every dated row with a `fee_display`. While looping, collect per player the dates of non-loan rows whose `fee_display.strip().lower()` starts with `"free"`. After `best` is settled, add `"later_free_move": "<iso date>" | None` to each row: the newest such date more than 60 days after the winning fee's date. Additive key; existing keys and the display behaviour are unchanged (`test_the_newest_paid_move_wins_and_loans_and_free_moves_dont_count` must still pass untouched — the "Last transfer" cell keeps showing the last *paid* move).
- `inputs_v2.LastFee`: add `later_free_move: str | None = None` at the end (so stored snapshots without it still load).
- `features_v2.build_last_fee`: pass it through. The backtest's `prev_fee` passes `None`.
- `engine_v2.fee_anchor`: check it first, straight after the "no fee" guard.
- Tests: engine (skipped, reason names the year, value unchanged); `test_last_fee.py` (free move after the fee sets the key; a free move *before* the fee does not; a loan after the fee does not); replay test still exact.
- Outcome report: the new reason appears in "Skipped, by reason" automatically.

### R4. Honest skip reasons

In `fee_anchor`, when `weight < FEE_ANCHOR_MIN_WEIGHT`, name the factor that did the most damage instead of one catch-all sentence:

| Smallest of | Reason |
|---|---|
| basis weight (`RELEASE_CLAUSE`) | "The {year} fee was a release clause, which says little about his market price" |
| evidence weight (known minutes between 450 and 1,800, or unknown) | "The {year} fee was paid on little playing time on record" |
| recency weight | "The {year} fee is too old to anchor on" |
| source credibility is 0 (unknown source key) | "The {year} fee is too weakly sourced to anchor on" |

Compare the four multipliers and take the smallest; ties go in the table's order. Update `test_old_reported_fee_is_not_applied_and_says_why` and add one test per reason. Update section 11.4's Haaland row expectation and the frontend test fixture if it quotes the old sentence. No `market-v3` row exists in production yet, so changing the text now costs nothing; after rollout it would leave two wordings in history.

### R5. Calibration: the right sample, and a tool to do it

Replaces the "Calibration rule" in B7.

- The deciding sample is **repeat transfers where the anchor was applied**. Print that n. Under 15 → keep the defaults, say so in the report, do not tune. The "all repeat transfers" line stays in the table for context, but for skipped rows `v3_anchor == v2_market` by construction, so it dilutes the comparison.
- Add `--grid` to `scripts/valuation_backtest.py`. It loads the comparables index **once**, then for each of `REPORTED` credibility {0.5, 0.65, 0.8, 0.9} × `FEE_ANCHOR_RECENCY_YEARS` {2, 3, 4, 5} recomputes the repeat-transfer metrics in memory and prints a 16-row table: n applied, ±25%, median |error|, bias, for `v3_anchor`, with `v2_market` on the same rows beside it (the applied set changes with the setting, so the baseline must be recomputed per row). Implement by giving `fee_anchor` two optional keyword overrides (`source_credibility: dict | None = None`, `recency_years: float | None = None`) that default to the constants — not by mutating module globals. Production behaviour is unchanged when they are omitted; add a test that says so.
- Decision rule, unchanged in spirit: pick by ±25% then |bias|; show the user the whole grid; if nothing beats `v2_market` on the applied rows, stop and tell the user. Never change a constant without the user seeing the grid.
- With small n, also print the applied rows themselves (player, earlier fee, later fee, both predictions). Twenty rows read better than a percentage.

### R6. Outcome report improvements (`scripts/valuation_outcome_report.py`)

1. **Rises and falls:** replace the single largest rise/fall with two tables, the 10 largest rises and the 10 largest falls among anchor-applied players (name, age, club, last fee and date, before, after, change, factor). The falls are where a cheap fee drags a good player down — the case to look at hardest, because the model assumes a fresh contract at the time of the fee and a cheap fee is often cheap for a reason (expiring deal, relegation clause).
2. **Bounds line:** print "Anchor factors: min ×{a} max ×{b} (bounds ×0.70–×1.60)" across all applied players — acceptance check 7 in one line.
3. **Name matching:** match in tiers and stop at the first tier that has hits: (a) whole name equals the fragment; (b) the fragment equals a whole word of the name ("Rice" in "D. Rice", not in "Price"); (c) substring. Within a tier keep "most minutes in the latest season". Cap "also matched" at 5 names plus "and N more".
4. **Coverage sentence** above the totals: "Pre-transfer stats exist from about the 2022 season, so older fees carry less weight and are often not used." (section 12 required it; the script omits it.)
5. **Read-only guard on the backtest too.** `valuation_backtest.py` has no `SET TRANSACTION READ ONLY`; add the same guard the report has, at the top of its session.
6. Unit-test the pure helpers that carry logic: the tiered matcher, `_lesser_known` (half applied, half skipped, deterministic) and `_gbp`. No database needed.

### R7. Test gaps

- `test_fee_anchor_worked_example`: Appendix B's numbers, computed from the real constants in the test (not pasted), asserting weight ≈ 0.310 and factor ≈ 1.297 within a tolerance; if the real `CONTRACT_KNOTS` give a different contract factor, correct Appendix B rather than the code.
- In `test_a_staff_entered_fee_round_trips_through_the_parser`, also assert `engine_v2.parse_fee(display, GBP_PER)` gives the same pounds — the comparables index reads manual rows through that parser.
- Known and accepted, document it in a comment rather than changing it: `build_comparables_index`'s "earlier fee" lookup for the backtest ignores the manual-shadow rule and treats every earlier row as `REPORTED`/`PERMANENT`. Production has no manual rows yet, so it cannot affect the gate.

### R8. The production run and the gate (replaces the log's §8)

**Ask the user two things before starting:** the Railway `DATABASE_PUBLIC_URL` (pasted into the session's environment only — A4), and which route to take.

| Route | What happens | Production change |
|---|---|---|
| **1 — deploy migration `0111` first (recommended)** | A pull request containing only `backend/migrations/versions/0111_manual_transfer_fees.py`. It is additive and nullable, and the code on `main` ignores the new columns. After Railway applies it, both scripts run from this working tree as they are | Yes — four nullable columns. **Only on the user's explicit instruction**; the user merges and deploys |
| **2 — run from a copy without the Phase C columns** | Copy `backend/` to the scratch directory (skip `__pycache__`, `.pytest_cache`). In the copy only: delete the four new `mapped_column`s from `app/players/models.py`; replace reads of `.fee_basis`, `.source_note` with `getattr(row, "<name>", None)` in `app/players/last_fee.py` and `app/valuation/features_v2.py`. Run the scripts with the copy as the working directory, and first confirm the copy is what is imported: `python -c "import app, sys; print(app.__file__)"` must print the scratch path (the repo is installed with `pip install -e`, so check — do not assume). Delete the copy afterwards | None |

Route 1 is simpler and is what "safe to deploy ahead of the code" was for. Route 2 touches nothing in production but its results come from a hand-edited copy; say so in the report header if it is used.

Then, with `DATABASE_URL`, `JWT_SECRET_KEY` and `PYTHONUTF8` set, and under A4's hard rules:

```powershell
& $conda run --no-capture-output -n transferx python -m scripts.valuation_backtest --csv $env:TEMP\backtest.csv
& $conda run --no-capture-output -n transferx python -m scripts.valuation_backtest --grid
& $conda run --no-capture-output -n transferx python -m scripts.valuation_outcome_report `
    --players "Haaland,Ronaldo,Rice,Palmer,Yamal,Bellingham,Saka" --also 6 `
    --out $env:TEMP\valuation_outcome_report.md
Remove-Item Env:DATABASE_URL
```

A5's baseline no longer exists to compare against (no pre-change run was recorded). Substitute: the first table's `v1`, `v2_intrinsic` and `v2_market` columns must match the October figures in section 1.2 in kind (n near 84, ±25% in the 26–31% range, £25m+ under-predicted by roughly a third). A large difference means something unintended changed — investigate before reading the new columns. `git stash` plus a run on `main` gives an exact baseline if the user wants one.

**Gate — stop here.** Show the user the outcome report, the repeat-transfer table and the grid, and ask section 11.5's three questions. Do not merge, recompute or tune until the user has answered. If the report contradicts section 11.4's expectations, report what the data shows.

### R9. Frontend follow-ups (`pages/admin/AdminPlayerDetailPage.tsx`)

- Label the note field "Source note (shown to clubs)" and keep the placeholder. The note is public by design (it is the provenance of a public number); staff must know not to put a private contact or a confidential source in it. `source_url` stays admin-only, as now — say so in a muted hint under the field.
- Confirm before "Remove", using the same `confirm({ title, message, confirmLabel })` helper as `AdminUsersPage.tsx`: "Remove this fee? His model value is recalculated straight away." Extend `AdminPlayerDetailPage.test.tsx` for the confirm step.
- Watch item, no change now: each add and delete rebuilds the whole comparables index inside the request (`compute_and_store_valuation(db, player)` with `comps=None`). Time it once against a realistic database; if it exceeds a few seconds, raise it with the user rather than optimising unasked.

### R10. Docs and log

- `docs/feature_spec/valuation/model.md`: replace the `TODO` backtest table with the real figures and their n; add the "moved on a free" rule and the four skip reasons.
- `docs/feature_spec/valuation/market-data.md` ("What was built"): add the free-move rule; state that `source_note` is shown to clubs and `source_url` is not.
- `docs/engineering/api-reference.md`, `docs/business/glossary.md`: the new reason wording only if they quote the old one.
- `docs/SESSION_HANDOVER.md` and `docs/feature_spec/valuation/execution-log.md`: append a dated section for this round (what changed, the production figures, the user's answers to the three questions, which R8 route was used). Correct the log's §8, which describes commands that fail before `0111` is deployed.

### R11. Additions to the acceptance checklist

| # | Check | Pass when |
|---|---|---|
| 14 | Free move after the fee | Engine and `last_fee` tests for R3 pass; the display tests are untouched |
| 15 | Skip reasons | One test per reason in R4; no recent fee is described as "too old" |
| 16 | Calibration evidence | The grid and the applied-row n were shown to the user; any changed constant traces to that grid |
| 17 | Production figures in the docs | No `TODO` left in `valuation/model.md`'s backtest table |
| 18 | Gate honoured | The user's answers to section 11.5 are recorded in the log before any merge |
| 19 | Clean tree | No report, CSV or scratch copy left in the repo |

---

## Addendum 2 — Decision: Route 1, deploy migration `0111` first (2026-11-11 10:22)

The product owner chose **Route 1** from R8 on 2026-11-11. Route 2 (the scratch copy) is dropped — do not build it. This addendum replaces R8's route table and changes the order in R1. The rest of Addendum 1 stands.

### S1. What is and is not authorised

| Action | Authorised? |
|---|---|
| Commit the migration file alone on its own branch, push it, open a pull request | **Yes** — this decision covers it |
| Merge that pull request (the merge is what deploys to Railway and alters the production table) | **The user merges.** Do not merge it yourself |
| Run `alembic` by hand against Railway | **No.** The container applies migrations on start (`backend/entrypoint.sh`) |
| Commit, push or merge anything else from `valuation-v3-fee-anchor` | **No** — still only when the user asks |
| Daily refresh, recompute, seed, backfill or repair scripts against Railway | **No** — A4's hard rules are unchanged |

### S2. Revised order of work

The migration does not depend on the code fixes, so start it first and do the local work while it deploys.

1. **S3** — open the migration-only pull request. Tell the user it is ready to merge.
2. R2–R7 — environment corrections, code and tests, all local (unchanged).
3. **S4** — once the user has merged and Railway has deployed, verify the columns exist.
4. **S5** — the production run and the gate.
5. R9, R10 — frontend follow-ups, docs and log.

### S3. The migration-only pull request

The whole feature is uncommitted in the main working tree. **Do not stash, switch branches or commit there** — use a separate worktree so that work cannot be disturbed.

```powershell
cd D:\Repo\transfer-x
git fetch origin
git worktree add -b migration-0111-manual-transfer-fees "$env:TEMP\tx-migration-0111" origin/main
Copy-Item backend\migrations\versions\0111_manual_transfer_fees.py `
    "$env:TEMP\tx-migration-0111\backend\migrations\versions\"
cd "$env:TEMP\tx-migration-0111"
git status --short        # expect exactly one untracked file: the migration
```

Before committing, check:

- Read `docs/engineering/database-migrations.md` and follow anything it requires of a migration-only change.
- `origin/main` must still end at revision `0110`. List `backend/migrations/versions/` in the worktree and open the newest numbered file; if someone has added a `0111` or later since 2026-11-10, **stop and tell the user** — the file needs renumbering and its `down_revision` changing, and the copy in the feature tree must be changed to match.
- The file's docstring says the vendor sync "now replaces only its own rows". That is not yet true on `main`. Reword that sentence in the worktree copy to "…and will survive the vendor sync once the code that reads these columns is deployed", and make the identical edit to the copy in `D:\Repo\transfer-x` so the two files stay byte-for-byte the same (S6 depends on it).
- The pull request must contain **one file**. No model change, no code, no docs: the ORM on `main` does not map the new columns and must keep ignoring them.

Commit, push and open the pull request (`gh pr create`), following the attribution rules of the session. Suggested title: "Migration 0111: staff-entered transfer fee columns (additive, ahead of the code)". The description should say:

- four nullable columns on `player_transfers` (`fee_basis`, `source_note`, `source_url`, `entered_by_user_id`) and one foreign key to `users` with `ON DELETE SET NULL`;
- no code reads or writes them yet, so behaviour is unchanged;
- why it ships alone: the read-only valuation backtest and outcome report on the feature branch need the columns to exist before they can run against production;
- rollback: the migration's `downgrade()` drops the constraint and the columns; nothing will have written to them.

Then tell the user the pull request is ready and wait. Remove the worktree when the pull request is merged: `git worktree remove "$env:TEMP\tx-migration-0111"`.

Why this is safe to deploy alone: adding nullable columns without defaults is a catalogue-only change in PostgreSQL (no table rewrite); the foreign key is validated against a column that is entirely `NULL`. Both take a brief lock on `player_transfers`, and the foreign key also on `users`.

### S4. Verify the deploy (read-only)

After the user confirms the merge and the Railway deploy has finished, with `DATABASE_URL`, `JWT_SECRET_KEY` and `PYTHONUTF8` set as in A4, from `D:\Repo\transfer-x\backend`:

```powershell
& $conda run --no-capture-output -n transferx python -c "import asyncio; from sqlalchemy import text; from app.database import AsyncSessionLocal
async def main():
    async with AsyncSessionLocal() as db:
        await db.execute(text('SET TRANSACTION READ ONLY'))
        cols = (await db.execute(text(\"select column_name from information_schema.columns where table_name = 'player_transfers' and column_name in ('fee_basis','source_note','source_url','entered_by_user_id') order by 1\"))).scalars().all()
        ver = (await db.execute(text('select version_num from alembic_version'))).scalars().all()
        print(cols, ver)
asyncio.run(main())"
```

Pass when all four column names are printed and the version is `0111`. If the quoting fights PowerShell, put the same code in a file in the scratch directory and run it from `backend/` — never in the repo. If the columns are missing, the deploy has not finished or failed: tell the user and stop; do not apply the migration by hand.

### S5. The production run

Exactly as the command block in R8, run from the main working tree (`D:\Repo\transfer-x\backend`) with the R3–R7 changes in place. The baseline substitute and the **gate — stop and show the user** paragraphs of R8 apply unchanged. The report header needs no "hand-edited copy" note, since Route 2 is not used.

### S6. Bringing the feature branch back in line with `main`

After the merge, `main` contains the migration file and the feature working tree holds an untracked copy of the same file, so git will refuse to merge or rebase over it. When the user asks for the feature to be committed:

1. Confirm the two are identical: `git diff --no-index backend\migrations\versions\0111_manual_transfer_fees.py <(git show origin/main:backend/migrations/versions/0111_manual_transfer_fees.py)` in Git Bash, or compare hashes. If they differ, `main` is the truth — it is what production ran.
2. Delete the untracked copy, then bring `origin/main` into `valuation-v3-fee-anchor`. The file returns as a tracked file.
3. The feature pull request must then show **no** migration in its diff. If the feature later needs a schema change, that is a new migration `0112`; never edit `0111` after it has run in production.

### S7. Corrections this decision makes elsewhere

- Section 4's Phase C row and C6's reminder ("read-only scripts cannot run against production until `0111` is deployed") are resolved by S3–S4.
- D3 step 1 becomes: "Merge the feature → Railway deploys. Migration `0111` is already applied; no schema change ships with the code."
- Appendix A: `0111_manual_transfer_fees.py` ships in its own pull request, ahead of Phase C's code.
- R10: record in the log the migration pull request's number, when it was merged, and the S4 verification output.

### S8. Additions to the acceptance checklist

| # | Check | Pass when |
|---|---|---|
| 20 | Migration pull request | Contains one file; opened by the agent, merged by the user |
| 21 | Deploy verified | S4 prints the four columns and version `0111`, before any script runs against production |
| 22 | Feature diff has no migration | After S6, `git diff origin/main --stat` on the feature branch lists no file under `backend/migrations/` |

---

## Addendum 3 — Review of Round 2 and what ships (2026-11-13)

Written after reviewing the uncommitted tree against `origin/main` at `15e6ba1`. **Where this addendum disagrees with anything above, this addendum wins.** Detail and figures are in `docs/feature_spec/valuation/execution-log.md`, Round 3.

### T1. What changed underneath the work

| Finding | Consequence |
|---|---|
| `main` gained `0111_move_reminders.py` on 2026-11-12 (S3 warned of this) | The staff-fee migration is now **`0112_manual_transfer_fees.py`, revising `0111`**. Shipping it as `0111` would have given Alembic two revisions with one id and stopped the API container at start |
| The migration-only pull request was never pushed | **Route 1 is dropped.** The migration ships in the same pull request as the code; `entrypoint.sh` applies it before the API starts. S3, S4, S6 and checks 20–22 no longer apply. The local branch `migration-0111-manual-transfer-fees` and its worktree are stale |
| `main` gained the type-and-colour guard (`frontend/src/test/designSystem.test.ts`) | The admin "Transfer fees" card and the popover's "Last fee not used" line use the type roles (`text-caption`, `text-small`, `text-input lg:text-body`); no raw sizes, no uppercase |
| The env file supplied on 2026-11-13 holds only the local Docker database (`db:5432`) | The production backtest and outcome report (B10, R8, S5) are **still not run**. Checks 6, 7, 8, 16, 17 and 18 stay open |

### T2. Decision: the anchor ships switched off

The gate in B10 and R8 is blocking and could not be run, and the change had to be safe to deploy the same day. So:

- `settings.valuation_fee_anchor_enabled` (`VALUATION_FEE_ANCHOR_ENABLED`, default **`false`**) in `backend/app/config.py`.
- While off, `valuation/service.py` does not load the last fee into the features, so `compute_valuation_v2` takes its no-fee path: the value, the drivers and the replay are exactly `market-v2`, the row is labelled `market-v2` (`MODEL_VERSION_WITHOUT_FEE_ANCHOR`), and `inputs_json["fee_anchor"]` is `null`.
- While on, everything is as sections 6–8 describe and rows are labelled `market-v3`.
- The test suite runs with the switch on (`tests/conftest.py`); `test_fee_anchor_switched_off_stores_a_market_v2_row` covers off.
- Staff-entered fees, the vendor-sync fix, the cache-freshness fix and the fee's provenance in the UI do not depend on the switch.
- The read-only scripts call the engine directly, so they report `market-v3` whatever the switch says.

This replaces "Feature flag: none" in the log's §7 and in D2's spec note.

### T3. Order of work from here

1. Commit and open one pull request when the user asks. Never add `ATT95143.env`.
2. Merge between the `stats-worker` refreshes (17:00 and 22:00 UK): the worker runs the new image without migrating, and its ORM reads the four new columns.
3. After the deploy, under A4's hard rules: the backtest, `--grid` and the outcome report against production, outputs to the temp directory. Fill the `TODO` table in `docs/feature_spec/valuation/model.md`.
4. **Gate, unchanged:** show the user the report, the repeat-transfer table and the grid; ask section 11.5's three questions; apply R5's calibration rule.
5. Only then set `VALUATION_FEE_ANCHOR_ENABLED=true` on `backend` and `stats-worker`.

### T4. Additions to the acceptance checklist

| # | Check | Pass when |
|---|---|---|
| 23 | One migration head | `alembic heads` prints `0112 (head)` only |
| 24 | Off means `market-v2` | `test_fee_anchor_switched_off_stores_a_market_v2_row` passes |
| 25 | Design guard | `npx vitest run src/test/designSystem.test.ts` passes with an empty allowlist |
| 26 | Switch turned on only after the gate | The log records the production figures and the user's answers before `VALUATION_FEE_ANCHOR_ENABLED=true` is set |
