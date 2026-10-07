"""Plausibility check: boxscore-v1 vs market-v2 on realistic player archetypes.

Not a backtest — the stat lines are approximate full-season profiles and the
"market" column is a rough public consensus range (GBP), there to show
direction and scale. The real backtest against recorded fees is
scripts/valuation_backtest.py, which needs the production database.

    python -m scripts.valuation_archetypes
"""

from datetime import datetime, timedelta, timezone

from app.valuation import engine as v1
from app.valuation import engine_v2
from app.valuation.features import FeatureSet
from app.valuation.inputs_v2 import FeatureSetV2, RecentGame, SeasonFeatures

FRESH = datetime.now(timezone.utc) - timedelta(days=5)


def season(
    pos,
    age,
    league,
    minutes,
    *,
    season=2025,
    rating=7.0,
    g=0,
    a=0,
    sot=0,
    kp=0,
    drb=0,
    pa=0.0,
    dw=0.0,
    defa=0,
    sv=0,
    gc=0,
    league_name=None,
) -> SeasonFeatures:
    n90 = minutes / 90
    fs = FeatureSet(
        player_id="x",
        position=pos,
        age=age,
        minutes=minutes,
        league_id=league,
        season=season,
        stats_updated_at=FRESH,
        avg_rating=rating,
        pass_accuracy=pa,
        duels_won_rate=dw,
        goals_per90=g / n90,
        assists_per90=a / n90,
        goals_plus_assists_per90=(g + a) / n90,
        shots_on_target_per90=sot / n90,
        key_passes_per90=kp / n90,
        dribbles_success_per90=drb / n90,
        defensive_actions_per90=defa / n90,
        saves_per90=sv / n90,
        goals_conceded_per90=gc / n90,
    )
    return SeasonFeatures(season, minutes, league, fs, league_name)


def v1_value(s: SeasonFeatures) -> float:
    score = v1.compute_performance_score(s.features)
    return v1.compute_fair_value(s.features, score).fair_value


ARCHETYPES = [
    # name, market range £m, FeatureSetV2 kwargs
    (
        "Elite PL striker, 25, 4y contract",
        (90, 130),
        dict(
            position="FWD",
            age=25,
            contract_years_remaining=4.0,
            seasons=[
                season("FWD", 25, "39", 2800, rating=7.5, g=23, a=6, sot=50, kp=40, drb=45),
                season(
                    "FWD", 24, "39", 2600, season=2024, rating=7.3, g=21, a=2, sot=45, kp=30, drb=40
                ),
            ],
        ),
    ),
    (
        "Wonderkid winger, 18, La Liga",
        (130, 200),
        dict(
            position="FWD",
            age=18,
            contract_years_remaining=5.0,
            seasons=[
                season("FWD", 18, "140", 2900, rating=7.9, g=9, a=13, sot=30, kp=80, drb=110),
                season(
                    "FWD", 17, "140", 2400, season=2024, rating=7.3, g=6, a=8, sot=20, kp=55, drb=80
                ),
            ],
        ),
    ),
    (
        "Elite PL midfielder, 26",
        (80, 110),
        dict(
            position="MID",
            age=26,
            contract_years_remaining=3.5,
            seasons=[
                season("MID", 26, "39", 2900, rating=7.4, g=7, a=8, kp=60, pa=88, dw=0.56, defa=110)
            ],
        ),
    ),
    (
        "Elite striker, 33, La Liga",
        (12, 25),
        dict(
            position="FWD",
            age=33,
            contract_years_remaining=1.0,
            seasons=[season("FWD", 33, "140", 2700, rating=7.4, g=25, a=4, sot=55, kp=30, drb=15)],
        ),
    ),
    (
        "Solid PL centre-back, 28",
        (30, 45),
        dict(
            position="DEF",
            age=28,
            contract_years_remaining=3.0,
            seasons=[season("DEF", 28, "39", 3000, rating=7.0, g=2, a=1, pa=90, dw=0.62, defa=140)],
        ),
    ),
    (
        "Average PL full-back, 30",
        (6, 14),
        dict(
            position="DEF",
            age=30,
            contract_years_remaining=2.0,
            seasons=[season("DEF", 30, "39", 2200, rating=6.8, g=1, a=2, pa=82, dw=0.52, defa=85)],
        ),
    ),
    (
        "Championship striker, 24, 18 goals",
        (8, 18),
        dict(
            position="FWD",
            age=24,
            contract_years_remaining=2.5,
            seasons=[season("FWD", 24, "40", 3000, rating=7.1, g=18, a=4, sot=40, kp=30, drb=30)],
        ),
    ),
    (
        "Eredivisie attacking mid, 20",
        (25, 45),
        dict(
            position="MID",
            age=20,
            contract_years_remaining=3.0,
            seasons=[
                season("MID", 20, "88", 2500, rating=7.4, g=9, a=8, kp=65, pa=85, dw=0.50, defa=60),
                season(
                    "MID",
                    19,
                    "88",
                    1800,
                    season=2024,
                    rating=7.0,
                    g=4,
                    a=4,
                    kp=35,
                    pa=83,
                    dw=0.47,
                    defa=45,
                ),
            ],
        ),
    ),
    (
        "Elite PL goalkeeper, 30",
        (25, 40),
        dict(
            position="GK",
            age=30,
            contract_years_remaining=3.0,
            seasons=[season("GK", 30, "39", 3400, rating=7.0, sv=110, gc=35, pa=78)],
        ),
    ),
    (
        "Danish league striker, 22",
        (3, 9),
        dict(
            position="FWD",
            age=22,
            contract_years_remaining=3.0,
            seasons=[season("FWD", 22, "119", 2600, rating=7.2, g=16, a=5, sot=38, kp=28, drb=35)],
        ),
    ),
    (
        "Elite winger, 29, 6 months left",
        (25, 45),
        dict(
            position="FWD",
            age=29,
            contract_years_remaining=0.5,
            seasons=[season("FWD", 29, "39", 2700, rating=7.4, g=15, a=10, sot=40, kp=60, drb=70)],
        ),
    ),
    (
        "Same winger, 29, 4 years left",
        (55, 80),
        dict(
            position="FWD",
            age=29,
            contract_years_remaining=4.0,
            seasons=[season("FWD", 29, "39", 2700, rating=7.4, g=15, a=10, sot=40, kp=60, drb=70)],
        ),
    ),
    (
        "PL midfielder, 26, injury-prone (60%)",
        (20, 35),
        dict(
            position="MID",
            age=26,
            contract_years_remaining=3.0,
            games_missed_injured=30,
            games_available_total=76,
            seasons=[
                season("MID", 26, "39", 1500, rating=7.1, g=4, a=4, kp=30, pa=87, dw=0.52, defa=45)
            ],
        ),
    ),
    (
        "Teen breakout, 19, 600 PL minutes",
        (15, 35),
        dict(
            position="FWD",
            age=19,
            contract_years_remaining=4.0,
            recent_games=[RecentGame(7.8, 80), RecentGame(7.5, 70), RecentGame(7.2, 90)],
            seasons=[season("FWD", 19, "39", 600, rating=7.2, g=4, a=1, sot=9, kp=7, drb=12)],
        ),
    ),
]


def main() -> None:
    print(f"{'Archetype':42} {'Market £m':>11} {'v1 £m':>8} {'v2 £m':>8}  v2 range")
    for name, (lo, hi), kwargs in ARCHETYPES:
        fs = FeatureSetV2(player_id="x", **kwargs)
        out = engine_v2.compute_valuation_v2(fs)
        v1v = v1_value(fs.seasons[0])
        inside = "✓" if lo <= out.fair_value / 1e6 <= hi else " "
        print(
            f"{name:42} {f'{lo}-{hi}':>11} {v1v / 1e6:8.1f} {out.fair_value / 1e6:8.1f} {inside} "
            f"{out.fair_value_low / 1e6:.1f}–{out.fair_value_high / 1e6:.1f}"
        )


if __name__ == "__main__":
    main()
