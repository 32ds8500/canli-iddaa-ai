import math

import pytest

from app.eval.metrics import (
    brier_score,
    calibration_buckets,
    log_loss,
    publishable,
    summarize,
)


def test_brier_known_answers():
    assert brier_score([1.0, 0.0], [1, 0]) == 0.0
    assert brier_score([0.0, 1.0], [1, 0]) == 1.0
    assert brier_score([0.5, 0.5], [1, 0]) == pytest.approx(0.25)


def test_log_loss_known_answer():
    # iki ornek, ikisi de 0.5 ve biri 1 biri 0 -> ln(2)
    assert log_loss([0.5, 0.5], [1, 0]) == pytest.approx(math.log(2), rel=1e-6)


def test_calibration_buckets():
    # 0.05 ve 0.05 ayni kovaya (0-0.1), 0.85 ve 0.85 ayni kovaya (0.8-0.9)
    probs = [0.05, 0.05, 0.85, 0.85]
    outcomes = [0, 0, 1, 1]
    buckets = calibration_buckets(probs, outcomes, n_buckets=10)
    assert len(buckets) == 2
    assert buckets[0].count == 2
    assert buckets[0].actual_rate == 0.0
    assert buckets[1].actual_rate == 1.0


def test_publishable_threshold():
    small = summarize([0.5] * 5, [1, 0, 1, 0, 1])
    assert publishable(small) is False
    big = summarize([0.5] * 30, [1, 0] * 15)
    assert publishable(big) is True


def test_summary_baseline_present():
    s = summarize([0.6, 0.4, 0.7], [1, 0, 1])
    assert s.count == 3
    assert 0 <= s.brier <= 1
    assert s.baseline_brier >= 0
