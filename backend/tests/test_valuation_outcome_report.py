"""Pure helpers of the valuation outcome report (no database needed)."""

from types import SimpleNamespace

from scripts.valuation_outcome_report import _gbp, _lesser_known, _match_named


def _result(
    pid: str,
    name: str,
    *,
    minutes: int = 2000,
    applied: bool = True,
    value: float = 10_000_000.0,
    coef: float = 0.5,
) -> SimpleNamespace:
    player = SimpleNamespace(
        id=pid, name=name, age=25, position=None, current_club_id=None, team_name=None
    )
    fee = SimpleNamespace(fee_gbp=10_000_000.0, transfer_date="2023-07-01")
    features = SimpleNamespace(
        seasons=[SimpleNamespace(minutes=minutes)], last_fee=fee, age=25
    )
    anchor = SimpleNamespace(applied=applied)
    after = SimpleNamespace(
        fee_anchor=anchor, league_coefficient=coef, fair_value=value
    )
    before = SimpleNamespace(fair_value=value)
    return SimpleNamespace(
        player=player, features=features, before=before, after=after, no_valuation=None
    )


def test_gbp_formats_millions_and_thousands():
    assert _gbp(None) == "—"
    assert _gbp(1_500_000) == "£1.5m"
    assert _gbp(750_000) == "£750k"


def test_name_matching_prefers_a_whole_word_over_a_substring():
    declan = _result("1", "Declan Rice", minutes=2000)
    price = _result("2", "Richard Price", minutes=4000)
    maurice = _result("3", "Maurice", minutes=4000)
    chosen, also = _match_named([declan, price, maurice], "Rice")
    assert chosen is declan
    assert also == []


def test_name_matching_takes_the_whole_name_first():
    declan = _result("1", "Declan Rice", minutes=500)
    initial = _result("2", "D. Rice", minutes=4000)
    chosen, _ = _match_named([declan, initial], "Declan Rice")
    assert chosen is declan


def test_name_matching_falls_back_to_a_substring():
    sakamoto = _result("1", "Ryo Sakamoto", minutes=2000)
    chosen, also = _match_named([sakamoto], "Saka")
    assert chosen is sakamoto
    assert also == []


def test_name_matching_breaks_ties_by_minutes():
    low = _result("1", "D. Rice", minutes=500)
    high = _result("2", "Declan Rice", minutes=4000)
    chosen, also = _match_named([low, high], "Rice")
    assert chosen is high
    assert also == [low]


def test_lesser_known_picks_half_applied_half_skipped_deterministically():
    results = [
        _result("1", "A", applied=True),
        _result("2", "B", applied=True),
        _result("3", "C", applied=True),
        _result("4", "D", applied=False),
        _result("5", "E", applied=False),
        _result("6", "F", applied=False),
    ]
    picked = _lesser_known(results, 4, set())
    assert len(picked) == 4
    assert sum(r.after.fee_anchor.applied for r in picked) == 2
    assert sum(not r.after.fee_anchor.applied for r in picked) == 2
    assert [r.player.id for r in picked] == [
        r.player.id for r in _lesser_known(results, 4, set())
    ]
