import pytest

from app.engines.baselines import prior_baseline
from app.engines.corner_model import CornerModel
from tests.helpers import make_features


def _probs(result):
    return {p.market: p.probability for p in result.predictions}


def test_all_probabilities_in_range():
    feats = make_features(minute=35, corners_home=2, corners_away=1, w10_home_corners=1, w10_away_corners=1)
    res = CornerModel().run(feats, prior_baseline("203"))
    assert res.sufficient
    for p in res.predictions:
        assert 0.0 <= p.probability <= 1.0


def test_horizons_monotonic():
    feats = make_features(minute=20)
    probs = _probs(CornerModel().run(feats, prior_baseline("203")))
    assert probs["corner_next_5_min"] <= probs["corner_next_10_min"] <= probs["corner_next_15_min"]


def test_expected_values_present_and_consistent():
    feats = make_features(minute=30, corners_home=3, corners_away=2)
    res = CornerModel().run(feats, prior_baseline("203"))
    exp = res.expected
    assert exp["corner_expected_match_total"] == pytest.approx(
        exp["corner_expected_rest_total"] + 5, abs=1e-6
    )
    assert exp["corner_expected_rest_home"] + exp["corner_expected_rest_away"] == pytest.approx(
        exp["corner_expected_rest_total"], abs=1e-6
    )


def test_thresholds_ordering():
    feats = make_features(minute=60, corners_home=4, corners_away=3)
    probs = _probs(CornerModel().run(feats, prior_baseline("203")))
    assert probs["corners_total_over_7_5"] >= probs["corners_total_over_8_5"]
    assert probs["corners_total_over_8_5"] >= probs["corners_total_over_9_5"]


def test_insufficient_without_live_stats():
    res = CornerModel().run(make_features(has_live_stats=False), prior_baseline("203"))
    assert res.sufficient is False
    assert res.predictions == []


def test_clustering_note_when_many_recent_corners():
    feats = make_features(minute=40, w10_home_corners=2, w10_away_corners=2)
    res = CornerModel().run(feats, prior_baseline("203"))
    assert any("kumelenme" in f.lower() for f in res.factors)
