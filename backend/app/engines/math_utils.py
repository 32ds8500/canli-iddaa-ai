"""Kucuk istatistik yardimcilari (Poisson)."""
from __future__ import annotations

import math


def poisson_pmf(k: int, mean: float) -> float:
    if mean <= 0:
        return 1.0 if k == 0 else 0.0
    return math.exp(-mean) * mean**k / math.factorial(k)


def poisson_cdf(k: int, mean: float) -> float:
    if k < 0:
        return 0.0
    return sum(poisson_pmf(i, mean) for i in range(0, k + 1))


def poisson_sf(k: int, mean: float) -> float:
    """P(X > k)"""
    if k < 0:
        return 1.0
    return max(0.0, 1.0 - poisson_cdf(k, mean))


def prob_at_least_one(rate_per_minute: float, minutes: float) -> float:
    """Oran * sure Poisson sureci icin P(en az bir olay)."""
    if rate_per_minute <= 0 or minutes <= 0:
        return 0.0
    return 1.0 - math.exp(-rate_per_minute * minutes)


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))
