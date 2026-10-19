import pytest

from app.engines.baselines import prior_baseline
from app.engines.goal_model import GoalModel
from tests.helpers import make_features


def _probs(result):
    return {p.market: p.probability for p in result.predictions}


def test_all_probabilities_in_range():
    feats = make_features(minute=40, score_home=1, score_away=1, w10_home_shots_on=3, w10_away_shots_on=2)
    res = GoalModel().run(feats, prior_baseline("203"))
    assert res.sufficient
    assert res.predictions
    for p in res.predictions:
        assert 0.0 <= p.probability <= 1.0


def test_horizons_monotonic():
    feats = make_features(minute=30, w10_home_shots_on=1, w10_away_shots_on=1)
    probs = _probs(GoalModel().run(feats, prior_baseline("203")))
    assert probs["goal_next_5_min"] <= probs["goal_next_10_min"] <= probs["goal_next_15_min"]


def test_next_goal_probabilities_sum_to_one():
    feats = make_features(minute=55, score_home=0, score_away=1)
    probs = _probs(GoalModel().run(feats, prior_baseline("203")))
    assert probs["goal_next_home"] + probs["goal_next_away"] == pytest.approx(1.0, abs=1e-6)


def test_red_card_reduces_home_attack():
    base = _probs(GoalModel().run(make_features(minute=50), prior_baseline("203")))
    red = _probs(GoalModel().run(make_features(minute=50, home_red=1), prior_baseline("203")))
    assert red["goal_home_rest"] < base["goal_home_rest"]
    assert red["goal_away_rest"] > base["goal_away_rest"]


def test_insufficient_without_live_stats():
    res = GoalModel().run(make_features(has_live_stats=False, minute=30), prior_baseline("203"))
    assert res.sufficient is False
    assert res.predictions == []


def test_total_goals_thresholds_ordering():
    feats = make_features(minute=70, score_home=2, score_away=1)
    probs = _probs(GoalModel().run(feats, prior_baseline("203")))
    assert probs["goals_total_over_1_5"] >= probs["goals_total_over_2_5"]
    assert probs["goals_total_over_2_5"] >= probs["goals_total_over_3_5"]
    # mevcut toplam 3 -> 3.5 ustu < 1
    assert probs["goals_total_over_3_5"] < 1.0


def test_high_scoring_game_total_floor():
    # 5 gol atilmis; 4.5 alt esigi kesin asilmis olmali (olasilik ~1, mevcut > th oldugu icin)
    feats = make_features(minute=80, score_home=3, score_away=2)
    probs = _probs(GoalModel().run(feats, prior_baseline("203")))
    assert probs["goals_total_over_4_5"] == pytest.approx(1.0)
