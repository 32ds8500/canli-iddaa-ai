"""Tahmin performans metrikleri (gercek sonuclara gore)."""
from __future__ import annotations

import math
from dataclasses import dataclass

EPS = 1e-15


def _clip(p: float) -> float:
    return min(1 - EPS, max(EPS, p))


def brier_score(probs: list[float], outcomes: list[int]) -> float:
    if not probs:
        raise ValueError("Bos girdi")
    return sum((p - o) ** 2 for p, o in zip(probs, outcomes)) / len(probs)


def log_loss(probs: list[float], outcomes: list[int]) -> float:
    if not probs:
        raise ValueError("Bos girdi")
    total = 0.0
    for p, o in zip(probs, outcomes):
        pc = _clip(p)
        total += -(o * math.log(pc) + (1 - o) * math.log(1 - pc))
    return total / len(probs)


@dataclass
class CalibrationBucket:
    low: float
    high: float
    count: int
    avg_predicted: float
    actual_rate: float


def calibration_buckets(
    probs: list[float], outcomes: list[int], n_buckets: int = 10
) -> list[CalibrationBucket]:
    buckets: list[list[tuple[float, int]]] = [[] for _ in range(n_buckets)]
    for p, o in zip(probs, outcomes):
        idx = min(n_buckets - 1, int(p * n_buckets))
        buckets[idx].append((p, o))
    out: list[CalibrationBucket] = []
    width = 1.0 / n_buckets
    for i, items in enumerate(buckets):
        if not items:
            continue
        avg_p = sum(p for p, _ in items) / len(items)
        rate = sum(o for _, o in items) / len(items)
        out.append(
            CalibrationBucket(
                low=round(i * width, 4),
                high=round((i + 1) * width, 4),
                count=len(items),
                avg_predicted=round(avg_p, 4),
                actual_rate=round(rate, 4),
            )
        )
    return out


@dataclass
class PerformanceSummary:
    count: int
    brier: float
    log_loss: float
    base_rate: float
    baseline_brier: float  # sabit taban orani tahmini ile
    baseline_log_loss: float
    buckets: list[CalibrationBucket]


def summarize(probs: list[float], outcomes: list[int], n_buckets: int = 10) -> PerformanceSummary:
    if not probs:
        raise ValueError("Bos girdi")
    base_rate = sum(outcomes) / len(outcomes)
    return PerformanceSummary(
        count=len(probs),
        brier=round(brier_score(probs, outcomes), 5),
        log_loss=round(log_loss(probs, outcomes), 5),
        base_rate=round(base_rate, 4),
        baseline_brier=round(
            brier_score([base_rate] * len(probs), outcomes), 5
        ),
        baseline_log_loss=round(log_loss([base_rate] * len(probs), outcomes), 5),
        buckets=calibration_buckets(probs, outcomes, n_buckets),
    )


MIN_SAMPLE_FOR_REPORT = 30


def publishable(summary: PerformanceSummary) -> bool:
    """Yetersiz ornekte performans yuzdesi yayinlanmaz."""
    return summary.count >= MIN_SAMPLE_FOR_REPORT
