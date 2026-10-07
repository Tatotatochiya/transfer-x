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
from collections import defaultdict

from app.valuation import engine as v1
from app.valuation import engine_v2
from app.valuation.inputs_v2 import CompRecord


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


def backtest_rows(comps: list[CompRecord]) -> list[dict]:
    """Per-transfer predictions from each model vs the fee actually paid."""
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
                "v2_market": comp.intrinsic_gbp * market.factor,
                "comps_used": market.comps_used,
            }
        )
    return rows


async def run(csv_path: str | None) -> None:
    import app.main  # noqa: F401 — registers every ORM model before querying
    from app.database import AsyncSessionLocal
    from app.valuation.features_v2 import build_comparables_index

    async with AsyncSessionLocal() as db:
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

    def line(label: str, subset: list[dict]) -> None:
        cells = []
        for m in models:
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

    if csv_path:
        with open(csv_path, "w", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        print(f"\nPer-transfer rows written to {csv_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--csv", help="also write per-transfer predictions to this CSV")
    asyncio.run(run(parser.parse_args().csv))
