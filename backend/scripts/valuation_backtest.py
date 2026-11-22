"""Backtest boxscore-v1 vs market-v2 against recorded transfer fees.

For every fee-bearing permanent transfer in the comparables window (TransferX
completed deals + vendor-reported fees), predict the fee from the stats the
buyer had at the time and compare with what was actually paid (restated in
today's money):

  v1          boxscore-v1 on the pre-transfer season (single season, step age)
  v2 intrinsic market-v2 before the market-rate step
  v2 + market  intrinsic × market rate from the OTHER comparables
              (leave-one-player-out, so a transfer never prices itself)

Contract length, form and availability at the time of each move are not
reconstructable, so neither model gets them — this measures the performance /
age / league / market core.

Read-only. Run against any environment's database:

    cd backend && python -m scripts.valuation_backtest            # summary
    python -m scripts.valuation_backtest --csv backtest.csv       # + per-transfer rows
"""

import argparse
import asyncio
import csv
import math
import statistics
from collections import Counter, defaultdict

from sqlalchemy import text

from app.valuation import engine as v1
from app.valuation import engine_v2
from app.valuation.inputs_v2 import CompRecord

# Calibration sweep for the repeat-transfer sample (R5): REPORTED-fee
# credibility × how fast the weight decays with the age of the fee.
GRID_CREDIBILITY = (0.50, 0.65, 0.80, 0.90)
GRID_RECENCY_YEARS = (2.0, 3.0, 4.0, 5.0)
# The plan keeps the defaults unless at least this many repeat transfers have
# the anchor applied; below it, the grid is read, not acted on.
MIN_CALIBRATION_N = 15


def _gbp_m(value: float) -> str:
    return f"£{value / 1e6:.1f}m"


def _metrics(pairs: list[tuple[float, float]]) -> dict:
    """pairs of (predicted, actual) → accuracy summary on the log scale."""
    errs = [math.log(p / a) for p, a in pairs if p > 0 and a > 0]
    if not errs:
        return {"n": 0}
    abs_errs = [abs(e) for e in errs]
    return {
        "n": len(errs),
        "median_abs_err_pct": round((math.exp(statistics.median(abs_errs)) - 1) * 100, 1),
        "within_25pct": round(100 * sum(e <= math.log(1.25) for e in abs_errs) / len(errs), 1),
        "within_50pct": round(100 * sum(e <= math.log(1.5) for e in abs_errs) / len(errs), 1),
        # > 0: model over-predicts fees; < 0: under-predicts
        "median_bias_pct": round((math.exp(statistics.median(errs)) - 1) * 100, 1),
    }


def backtest_rows(
    comps: list[CompRecord],
    *,
    source_credibility: dict[str, float] | None = None,
    recency_years: float | None = None,
) -> list[dict]:
    """Per-transfer predictions from each model vs the fee actually paid.

    The two overrides drive the --grid calibration sweep; omitted, the anchor
    uses its constants exactly as production does."""
    rows = []
    for comp in comps:
        if comp.reference is None:
            continue
        ref = comp.reference.features
        ref.age = comp.age_at_transfer
        v1_pred = v1.compute_fair_value(ref, v1.compute_performance_score(ref)).fair_value
        market = engine_v2.market_rate(
            comps,
            player_id=comp.player_id,
            position=comp.position,
            age=comp.age_at_transfer,
            score=comp.score_at_transfer,
            coef=comp.league_coefficient,
        )
        v2_market = comp.intrinsic_gbp * market.factor
        anchor = engine_v2.fee_anchor(
            comp.prev_fee,
            position=comp.position,
            age=comp.age_at_transfer,
            score=comp.score_at_transfer,
            coef=comp.league_coefficient,
            contract_f=1.0,
            availability_f=1.0,
            value_before=v2_market,
            source_credibility=source_credibility,
            recency_years=recency_years,
        )
        rows.append(
            {
                "player": comp.player_name,
                "position": comp.position,
                "age": comp.age_at_transfer,
                "date": comp.transfer_date,
                "source": comp.source,
                "fee_display": comp.fee_display,
                "actual": comp.fee_gbp_today,
                "v1": v1_pred,
                "v2_intrinsic": comp.intrinsic_gbp,
                "v2_market": v2_market,
                "comps_used": market.comps_used,
                "prev_fee_gbp": comp.prev_fee.fee_gbp if comp.prev_fee else None,
                "prev_fee_date": comp.prev_fee.transfer_date if comp.prev_fee else None,
                "v3_anchor": v2_market * anchor.factor,
                "anchor_applied": anchor.applied,
                "anchor_reason": anchor.reason,
            }
        )
    return rows


def _grid(comps: list[CompRecord]) -> None:
    """R5: sweep REPORTED credibility × recency years on the repeat-transfer
    sample. The applied set changes with each setting, so v2_market is
    recomputed on the same rows for a like-for-like comparison."""
    print(
        "\nCalibration grid — the repeat transfers where the anchor is applied"
        "\nThe deciding sample changes with each setting, so v2_market is recomputed"
        " on the same rows. Small n means read it, do not tune."
    )
    print(
        f"\n{'REPORTED':>9} {'recency':>8} {'n':>5}"
        f" {'v3 ±25%':>9} {'v3 med':>8} {'v3 bias':>8}"
        f" {'v2 ±25%':>9} {'v2 med':>8} {'v2 bias':>8}"
    )

    def fmt(stats: dict, key: str) -> str:
        return "—" if stats["n"] == 0 else str(stats[key])

    default_credibility = dict(engine_v2.FEE_ANCHOR_SOURCE_CREDIBILITY)
    for cred in GRID_CREDIBILITY:
        for recency in GRID_RECENCY_YEARS:
            rows = backtest_rows(
                comps,
                source_credibility={**default_credibility, "REPORTED": cred},
                recency_years=recency,
            )
            applied = [
                r for r in rows if r["prev_fee_gbp"] is not None and r["anchor_applied"]
            ]
            v3 = _metrics([(r["v3_anchor"], r["actual"]) for r in applied])
            v2 = _metrics([(r["v2_market"], r["actual"]) for r in applied])
            print(
                f"{cred:>9.2f} {recency:>8.0f} {v3['n']:>5}"
                f" {fmt(v3, 'within_25pct'):>9} {fmt(v3, 'median_abs_err_pct'):>8}"
                f" {fmt(v3, 'median_bias_pct'):>8}"
                f" {fmt(v2, 'within_25pct'):>9} {fmt(v2, 'median_abs_err_pct'):>8}"
                f" {fmt(v2, 'median_bias_pct'):>8}"
            )


async def run(csv_path: str | None, grid: bool = False) -> None:
    import app.main  # noqa: F401 — registers every ORM model before querying
    from app.database import AsyncSessionLocal
    from app.valuation.features_v2 import build_comparables_index

    async with AsyncSessionLocal() as db:
        if db.bind is not None and db.bind.dialect.name == "postgresql":
            await db.execute(text("SET TRANSACTION READ ONLY"))
        comps = await build_comparables_index(db)
    rows = backtest_rows(comps)
    if not rows:
        print(
            "No fee-bearing transfers with pre-transfer stats in the window — nothing to backtest."
        )
        return

    print(f"\n{len(rows)} transfers backtested\n")
    models = ("v1", "v2_intrinsic", "v2_market")
    header = f"{'segment':22}" + "".join(f"{m:>36}" for m in models)
    print(header)
    print(f"{'':22}" + "   n  med|err|  ±25%   ±50%    bias" * len(models))

    def line(label: str, subset: list[dict], which=models) -> None:
        cells = []
        for m in which:
            s = _metrics([(r[m], r["actual"]) for r in subset])
            if s["n"] == 0:
                cells.append(f"{'—':>36}")
            else:
                cells.append(
                    f"{s['n']:>5} {s['median_abs_err_pct']:>7}% {s['within_25pct']:>5}% "
                    f"{s['within_50pct']:>5}% {s['median_bias_pct']:>+6}%"
                )
        print(f"{label:22}" + "".join(cells))

    line("ALL", rows)
    by: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by[f"pos {r['position']}"].append(r)
        band = "≤21" if r["age"] <= 21 else "22-27" if r["age"] <= 27 else "28+"
        by[f"age {band}"].append(r)
        fee_band = "<£5m" if r["actual"] < 5e6 else "£5-25m" if r["actual"] < 25e6 else "£25m+"
        by[f"fee {fee_band}"].append(r)
        by[f"source {r['source']}"].append(r)
    for key in sorted(by):
        line(key, by[key])

    # ── market-v3: the last-fee anchor on repeat transfers ────────────────────
    repeats = [r for r in rows if r["prev_fee_gbp"] is not None]
    print(
        f"\nRepeat transfers (players with an earlier fee) — n={len(repeats)}"
        "\nEach later fee is predicted with and without the player's own earlier fee."
    )
    if repeats:
        both = ("v2_market", "v3_anchor")
        print(f"{'segment':22}" + "".join(f"{m:>36}" for m in both))
        print(f"{'':22}" + "   n  med|err|  ±25%   ±50%    bias" * len(both))
        line("ALL", repeats, both)
        line("anchor applied", [r for r in repeats if r["anchor_applied"]], both)
        line("anchor not applied", [r for r in repeats if not r["anchor_applied"]], both)
        print(
            "\nCaveat: the actual fee is in today's money and the earlier fee is restated to"
            " the transfer date. Fee inflation between the two dates scales both predictions"
            " equally, so v2_market vs v3_anchor is a fair comparison; neither includes"
            " contract, form or availability at the time."
        )
        applied = [r for r in repeats if r["anchor_applied"]]
        print(
            f"\nDeciding sample: repeat transfers with the anchor applied — n={len(applied)}."
            + (
                " Under 15: keep the default constants; do not tune."
                if len(applied) < MIN_CALIBRATION_N
                else ""
            )
        )
        if applied:
            print("\nThe applied rows (both models predict the later fee):")
            print(
                f"{'player':26}{'earlier fee':>26}{'later fee':>26}"
                f"{'v2_market':>12}{'v3_anchor':>12}"
            )
            for r in applied[:30]:
                earlier = f"£{r['prev_fee_gbp'] / 1e6:.1f}m {r['prev_fee_date'] or ''}".strip()
                later = f"£{r['actual'] / 1e6:.1f}m {r['date']}"
                print(
                    f"{r['player'][:25]:26}{earlier:>26}{later:>26}"
                    f"{_gbp_m(r['v2_market']):>12}{_gbp_m(r['v3_anchor']):>12}"
                )
            if len(applied) > 30:
                print(f"  … and {len(applied) - 30} more")
        skipped = [r for r in repeats if not r["anchor_applied"]]
        if skipped:
            print("\nWhy the anchor was not applied (repeat-transfer rows):")
            for reason, n in Counter(r["anchor_reason"] for r in skipped).most_common():
                print(f"  {n:>4}  {reason}")
    else:
        print(
            "No player in this database has two fee-bearing permanent moves — the anchor"
            " cannot be verified on repeat transfers here."
        )

    if grid:
        _grid(comps)

    if csv_path:
        with open(csv_path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        print(f"\nPer-transfer rows written to {csv_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--csv", help="also write per-transfer predictions to this CSV")
    parser.add_argument(
        "--grid",
        action="store_true",
        help="sweep REPORTED credibility × recency years on the anchor-applied rows",
    )
    args = parser.parse_args()
    asyncio.run(run(args.csv, args.grid))
