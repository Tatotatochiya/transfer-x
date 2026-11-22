"""Outcome report: what the last-fee anchor (market-v3) changes, for named players.

Read-only. For each player it prints the value before the change (market-v2)
and after it (market-v3) next to the real last fee, with the reason in plain
English; then a summary table, totals across every eligible player, and the
repeat-transfer backtest. Nothing is written to the database.

    cd backend && python -m scripts.valuation_outcome_report \
        --players "Haaland,Ronaldo,Rice,Palmer,Yamal" --also 6 \
        --out valuation_outcome_report.md
"""

import argparse
import asyncio
import re
import statistics
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select, text

from app.valuation import engine_v2
from app.valuation.constants import MIN_MINUTES
from app.valuation.constants_v2 import FEE_ANCHOR_FACTOR_BOUNDS
from app.valuation.features_v2 import MarketFeatureProvider, build_comparables_index

SOURCE_LABEL = {"TRANSFERX": "TransferX", "MANUAL": "Manual", "REPORTED": "API-Football"}
ANCHOR_SOURCE_WORD = {"TRANSFERX": "TransferX", "MANUAL": "manual", "REPORTED": "reported"}
LESSER_KNOWN_MAX_VALUE = 15_000_000.0
LESSER_KNOWN_MAX_COEF = 0.40
LESSER_KNOWN_MIN_MINUTES = 1800


def _gbp(value: float | None) -> str:
    if value is None:
        return "—"
    if value >= 1_000_000:
        return f"£{value / 1_000_000:,.1f}m"
    return f"£{value / 1_000:,.0f}k"


def _pct_change(before: float, after: float) -> float:
    return (after / before - 1) * 100 if before else 0.0


def _month_year(iso: str) -> str:
    try:
        return date.fromisoformat(iso).strftime("%b %Y")
    except ValueError:
        return iso


@dataclass
class PlayerResult:
    player: object
    features: object | None
    before: object | None
    after: object | None
    no_valuation: str | None  # plain-English reason when there is no number


async def _evaluate(db, provider, comps, last_fees, player) -> PlayerResult:
    features = await provider.get_features(db, player, last_fees)
    if features is None:
        return PlayerResult(player, None, None, None, "No valuation: no stats on record")
    if features.seasons[0].minutes < MIN_MINUTES:
        return PlayerResult(
            player,
            features,
            None,
            None,
            f"No valuation: under {MIN_MINUTES} minutes this season",
        )
    before = engine_v2.compute_valuation_v2(features, comps, use_fee_anchor=False)
    after = engine_v2.compute_valuation_v2(features, comps)
    return PlayerResult(player, features, before, after, None)


def _club_label(player, club_names: dict) -> str:
    name = club_names.get(player.current_club_id) or player.team_name
    return name or "—"


def _league_label(features) -> str | None:
    if features is None or not features.seasons:
        return None
    return features.seasons[0].league_name


def _age_label(result: PlayerResult) -> str:
    if result.features is not None and result.features.age is not None:
        return str(result.features.age)
    return str(result.player.age) if result.player.age is not None else "—"


def _position_label(player) -> str:
    return player.position.value if player.position is not None else "—"


def _anchor_cell(result: PlayerResult) -> str:
    if result.after is None:
        return "—"
    anchor = result.after.fee_anchor
    if results_no_fee(result):
        return "no fee"
    if anchor.applied:
        return f"applied ×{anchor.factor:.2f}"
    return "not used"


def results_no_fee(result: PlayerResult) -> bool:
    return result.features is not None and result.features.last_fee is None


def _last_transfer_line(result: PlayerResult) -> str | None:
    fee = result.features.last_fee if result.features is not None else None
    if fee is None:
        return None
    route = " → ".join(part for part in (fee.from_team, fee.to_team) if part)
    bits = [_gbp(fee.fee_gbp), _month_year(fee.transfer_date)]
    if route:
        bits.append(route)
    bits.append(f"source: {SOURCE_LABEL.get(fee.source, fee.source)}")
    return " · ".join(bits)


def _why_line(result: PlayerResult) -> str:
    if result.features is not None and result.features.last_fee is None:
        return "No fee on record — value unchanged"
    fee = result.features.last_fee if result.features is not None else None
    anchor = result.after.fee_anchor if result.after is not None else None
    if fee is None or anchor is None:
        return "No fee on record — value unchanged"
    if not anchor.applied:
        return f"Last fee not used: {anchor.reason}"
    word = ANCHOR_SOURCE_WORD.get(fee.source, fee.source)
    return (
        f"Last fee anchor ×{anchor.factor:.2f}. {_gbp(fee.fee_gbp)} in"
        f" {_month_year(fee.transfer_date)} is {_gbp(anchor.fee_today)} in today's money;"
        f" a {fee.years_since:.1f}-year-old {word} fee carries weight {anchor.weight:.2f}."
    )


def _player_block(result: PlayerResult, club_names: dict) -> list[str]:
    player = result.player
    club = _club_label(player, club_names)
    league = _league_label(result.features)
    place = f"{club} ({league})" if league else club
    lines = [f"{player.name} · {_age_label(result)} · {_position_label(player)} · {place}"]

    transfer = _last_transfer_line(result)
    if transfer:
        lines.append(f"  Last transfer      {transfer}")
    elif result.features is not None:
        lines.append("  Last transfer      No fee on record — value unchanged")

    if result.after is None:
        lines.append(f"  {result.no_valuation}")
        return lines

    before, after = result.before, result.after
    lines.append(f"  Before (market-v2) {_gbp(before.fair_value)}")
    change = _pct_change(before.fair_value, after.fair_value)
    lines.append(
        f"  After  (market-v3) {_gbp(after.fair_value)}"
        f"      range {_gbp(after.fair_value_low)} – {_gbp(after.fair_value_high)}"
        f"      change {change:+.0f}%"
    )
    lines.append(f"  Why                {_why_line(result)}")
    fee = result.features.last_fee if result.features is not None else None
    if fee is not None and fee.fee_gbp > 0:
        lines.append(
            f"  Gap to last fee    before {_pct_change(fee.fee_gbp, before.fair_value):+.0f}%"
            f"  →  after {_pct_change(fee.fee_gbp, after.fair_value):+.0f}%"
        )
    return lines


def _table(header: list[str], rows: list[list[str]]) -> list[str]:
    out = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    out += ["| " + " | ".join(row) + " |" for row in rows]
    return out


def _repeat_table(comps) -> list[str]:
    from scripts.valuation_backtest import _metrics, backtest_rows

    rows = [r for r in backtest_rows(comps) if r["prev_fee_gbp"] is not None]
    header = ["Segment", "n", "v2_market ±25%", "v2_market bias",
              "v3_anchor ±25%", "v3_anchor bias"]
    if not rows:
        return [
            "### Repeat transfers",
            "",
            "No player in this database has two fee-bearing permanent moves — the anchor "
            "cannot be verified on repeat transfers here (n=0).",
        ]

    def cell(subset: list[dict], model: str) -> tuple[str, str]:
        stats = _metrics([(r[model], r["actual"]) for r in subset])
        if stats["n"] == 0:
            return "—", "—"
        return f"{stats['within_25pct']:.1f}%", f"{stats['median_bias_pct']:+.1f}%"

    table_rows = []
    segments = (
        ("All repeat transfers", rows),
        ("Anchor applied", [r for r in rows if r["anchor_applied"]]),
        ("Anchor not applied", [r for r in rows if not r["anchor_applied"]]),
    )
    for label, subset in segments:
        v2_25, v2_bias = cell(subset, "v2_market")
        v3_25, v3_bias = cell(subset, "v3_anchor")
        table_rows.append([label, str(len(subset)), v2_25, v2_bias, v3_25, v3_bias])
    return [
        "### Repeat transfers (players with an earlier fee)",
        "",
        "Predict the later fee with and without the earlier one. The comparison is fair: "
        "fee inflation between the two dates scales both predictions equally. Neither "
        "includes contract, form or availability at the time. The deciding sample is "
        "the anchor-applied rows; under 15, the default constants stand.",
        "",
        *_table(header, table_rows),
    ]


def _totals(results: list[PlayerResult]) -> list[str]:
    valued = [r for r in results if r.after is not None]
    with_fee = [r for r in valued if r.features.last_fee is not None]
    applied = [r for r in with_fee if r.after.fee_anchor.applied]
    skipped = [r for r in with_fee if not r.after.fee_anchor.applied]
    changes = [
        (_pct_change(r.before.fair_value, r.after.fair_value), r) for r in valued
    ]
    applied_changes = [
        _pct_change(r.before.fair_value, r.after.fair_value) for r in applied
    ]
    lines = [
        "### Totals across every eligible player",
        "",
        f"- Players valued: {len(valued)}",
        f"- With a last fee: {len(with_fee)}",
        f"- Anchor applied: {len(applied)}",
        f"- Anchor skipped: {len(skipped)}",
    ]
    if skipped:
        counts = Counter(r.after.fee_anchor.reason for r in skipped)
        lines.append("- Skipped, by reason:")
        lines += [f"  - {reason}: {n}" for reason, n in counts.most_common()]
    if applied_changes:
        lines.append(f"- Median change where applied: {statistics.median(applied_changes):+.1f}%")
    if changes:
        moved = sum(1 for change, _ in changes if abs(change) > 10)
        lines.append(
            f"- Moved by more than 10%: {moved} of {len(valued)}"
            f" ({100 * moved / len(valued):.0f}%)"
        )
    factors = [r.after.fee_anchor.factor for r in applied]
    if factors:
        lo, hi = FEE_ANCHOR_FACTOR_BOUNDS
        lines.append(
            f"- Anchor factors: min ×{min(factors):.2f} max ×{max(factors):.2f}"
            f" (bounds ×{lo:.2f}–×{hi:.2f})"
        )
    return lines


def _movers(results: list[PlayerResult], club_names: dict) -> list[str]:
    """The 10 largest rises and the 10 largest falls among anchor-applied
    players. The falls matter most: a cheap fee pulling a good player down is
    usually cheap for a reason (expiring deal, relegation clause)."""
    applied = [r for r in results if r.after is not None and r.after.fee_anchor.applied]
    if not applied:
        return [
            "### Largest rises and falls",
            "",
            "No anchor was applied on this database.",
        ]
    header = ["Player", "Age", "Club", "Last fee", "Before", "After", "Change", "Factor"]

    def row(change: float, result: PlayerResult) -> list[str]:
        fee = result.features.last_fee
        return [
            result.player.name,
            _age_label(result),
            _club_label(result.player, club_names),
            f"{_gbp(fee.fee_gbp)} · {_month_year(fee.transfer_date)}",
            _gbp(result.before.fair_value),
            _gbp(result.after.fair_value),
            f"{change:+.0f}%",
            f"×{result.after.fee_anchor.factor:.2f}",
        ]

    changes = [
        (_pct_change(r.before.fair_value, r.after.fair_value), r) for r in applied
    ]
    rises = sorted(changes, key=lambda pair: (-pair[0], pair[1].player.name))[:10]
    falls = sorted(changes, key=lambda pair: (pair[0], pair[1].player.name))[:10]
    return [
        "### Largest rises (anchor applied)",
        "",
        *_table(header, [row(change, result) for change, result in rises]),
        "",
        "### Largest falls (anchor applied)",
        "",
        "A cheap fee pulling a good player down is the case to look at hardest:"
        " a fee is often cheap for a reason (an expiring deal, a relegation clause).",
        "",
        *_table(header, [row(change, result) for change, result in falls]),
    ]


_NAME_WORD_RE = re.compile(r"[^\W_]+")


def _match_named(
    results: list[PlayerResult], fragment: str
) -> tuple[PlayerResult | None, list[PlayerResult]]:
    """Match in tiers, stopping at the first that has hits: whole name, whole
    word, then substring. A bare substring makes "Rice" match "Price"; the
    word tier does not."""
    needle = fragment.strip().lower()
    if not needle:
        return None, []
    names = [(r, r.player.name.lower()) for r in results]
    tiers = (
        [r for r, name in names if name == needle],
        [r for r, name in names if needle in _NAME_WORD_RE.findall(name)],
        [r for r, name in names if needle in name],
    )
    matches = next((tier for tier in tiers if tier), [])
    if not matches:
        return None, []
    # Most minutes in his latest season wins; ties broken deterministically.
    matches.sort(
        key=lambda r: (
            -(r.features.seasons[0].minutes if r.features is not None else -1),
            str(r.player.id),
        )
    )
    return matches[0], matches[1:]


def _lesser_known(
    results: list[PlayerResult], count: int, exclude: set
) -> list[PlayerResult]:
    """Half with the anchor applied, half skipped, both in a stable order."""
    if count <= 0:
        return []
    candidates = [
        r
        for r in results
        if r.after is not None
        and r.features.last_fee is not None
        and r.features.seasons[0].minutes >= LESSER_KNOWN_MIN_MINUTES
        and (
            r.before.fair_value < LESSER_KNOWN_MAX_VALUE
            or r.after.league_coefficient <= LESSER_KNOWN_MAX_COEF
        )
        and r.player.id not in exclude
    ]
    candidates.sort(key=lambda r: str(r.player.id))
    applied = [r for r in candidates if r.after.fee_anchor.applied]
    skipped = [r for r in candidates if not r.after.fee_anchor.applied]
    want_applied = (count + 1) // 2
    want_skipped = count // 2
    picked = applied[:want_applied] + skipped[:want_skipped]
    if len(picked) < count:
        rest = [r for r in candidates if r not in picked]
        picked += rest[: count - len(picked)]
    picked.sort(key=lambda r: str(r.player.id))
    return picked


def _footer() -> str:
    lo, hi = FEE_ANCHOR_FACTOR_BOUNDS
    return (
        "> Model estimate — not an official valuation. The last fee is a reported figure "
        "unless marked TransferX or Manual. The anchor is bounded to "
        f"×{lo:.2f}–×{hi:.2f} and weighted by the age and source of the fee."
    )


async def run(args) -> None:
    import app.main  # noqa: F401 — registers every ORM model before querying
    from app.clubs.models import Club
    from app.database import AsyncSessionLocal
    from app.players.last_fee import last_transfer_fees
    from app.players.models import Player

    async with AsyncSessionLocal() as db:
        if db.bind is not None and db.bind.dialect.name == "postgresql":
            await db.execute(text("SET TRANSACTION READ ONLY"))

        players = (
            (await db.execute(select(Player).order_by(Player.name))).scalars().all()
        )
        player_ids = [p.id for p in players]
        last_fees = await last_transfer_fees(db, player_ids)
        comps = await build_comparables_index(db)
        club_names = dict((await db.execute(select(Club.id, Club.name))).all())

        provider = MarketFeatureProvider()
        print(f"Evaluating {len(players)} players…", file=sys.stderr)
        results = []
        for idx, player in enumerate(players, start=1):
            results.append(await _evaluate(db, provider, comps, last_fees, player))
            if idx % 250 == 0:
                print(f"  {idx}/{len(players)}", file=sys.stderr)

    fragments = [part for part in (args.players or "").split(",") if part.strip()]
    named: list[PlayerResult] = []
    matched_ids: set = set()
    blocks: list[str] = []
    named_misses: list[str] = []
    for fragment in fragments:
        chosen, also = _match_named(results, fragment)
        if chosen is None:
            named_misses.append(fragment.strip())
            continue
        named.append(chosen)
        matched_ids.add(chosen.player.id)
        if args.summary_only:
            continue
        blocks.append("\n".join(_player_block(chosen, club_names)))
        if also:
            names = ", ".join(r.player.name for r in also[:5])
            if len(also) > 5:
                names += f", and {len(also) - 5} more"
            blocks.append(f"  also matched: {names}")

    picked = _lesser_known(results, args.also, matched_ids)
    if not args.summary_only:
        for result in picked:
            blocks.append("\n".join(_player_block(result, club_names)))

    summary_results: list[PlayerResult] = []
    seen_ids: set = set()
    for result in named + picked:
        if result.player.id not in seen_ids:
            seen_ids.add(result.player.id)
            summary_results.append(result)

    summary_rows = []
    for result in summary_results:
        before = _gbp(result.before.fair_value) if result.before else "—"
        after = _gbp(result.after.fair_value) if result.after else "—"
        change = (
            f"{_pct_change(result.before.fair_value, result.after.fair_value):+.0f}%"
            if result.after
            else "—"
        )
        summary_rows.append(
            [
                result.player.name,
                _age_label(result),
                _club_label(result.player, club_names),
                _gbp(result.features.last_fee.fee_gbp) if results_has_fee(result) else "—",
                before,
                after,
                change,
                _anchor_cell(result),
            ]
        )

    named_section = [
        f"{fragment.strip()}: Not in the database" for fragment in named_misses
    ]
    detail = [] if args.summary_only else blocks
    doc = [
        "# Valuation outcome report — market-v2 vs market-v3",
        "",
        f"Generated {date.today().isoformat()} from a read-only database session.",
        "",
        "## Named players",
        "",
        *named_section,
        *detail,
        "",
        "## Summary",
        "",
        *_table(
            ["Player", "Age", "Club", "Last fee", "Before", "After", "Change", "Anchor"],
            summary_rows,
        ),
    ]
    if args.also and not picked:
        doc += ["", "No lesser-known players matched the pick rules."]
    doc += [
        "",
        "Pre-transfer stats exist from about the 2022 season, so older fees carry"
        " less weight and are often not used.",
        "",
        *_totals(results),
        "",
        *_movers(results, club_names),
        "",
        *_repeat_table(comps),
        "",
        _footer(),
        "",
    ]

    output = "\n".join(doc)
    print(output)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(output)
        print(f"\nWritten to {args.out}", file=sys.stderr)


def results_has_fee(result: PlayerResult) -> bool:
    return result.features is not None and result.features.last_fee is not None


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--players", default="", help="comma-separated name fragments to report by name"
    )
    parser.add_argument(
        "--also", type=int, default=6, help="lesser-known players to add (default 6)"
    )
    parser.add_argument("--out", help="also write the Markdown report to this path")
    parser.add_argument(
        "--summary-only", action="store_true", help="omit the per-player detail blocks"
    )
    asyncio.run(run(parser.parse_args()))
