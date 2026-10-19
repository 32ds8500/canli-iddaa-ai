import math

import pytest

from app.engines.math_utils import (
    poisson_cdf,
    poisson_pmf,
    poisson_sf,
    prob_at_least_one,
)


def test_pmf_sums_to_one():
    total = sum(poisson_pmf(k, 2.5) for k in range(0, 40))
    assert total == pytest.approx(1.0, abs=1e-9)


def test_cdf_sf_complement():
    mean = 1.7
    for k in range(0, 12):
        assert poisson_cdf(k, mean) + poisson_sf(k, mean) == pytest.approx(1.0, abs=1e-12)


def test_prob_at_least_one():
    assert prob_at_least_one(0.0, 10) == 0.0
    assert prob_at_least_one(0.1, 10) == pytest.approx(1 - math.exp(-1))
    # daha uzun sure -> daha yuksek olasilik
    assert prob_at_least_one(0.05, 15) > prob_at_least_one(0.05, 5)
