"""Performans raporlari: lig, dakika araligi, skor durumu ve market bazli.

Kural: Yeterli ornek olmayan segmentlerde yuzde YAYINLANMAZ; yalnizca
ornek sayisi ve 'yetersiz ornek' notu gosterilir.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.eval.metrics import MIN_SAMPLE_FOR_REPORT, PerformanceSummary, summarize
from app.models import League, Match, Prediction, PredictionOutcome


@dataclass
class Segment:
    key: str
    label: str
    count: int
    summary: PerformanceSummary | None
    note: str | None = None


MINUTE_BUCKETS = [
    (0, 15, "0-15"),
    (15, 30, "15-30"),
    (30, 45, "30-45"),
    (45, 60, "45-60"),
    (60, 75, "60-75"),
    (75, 200, "75-90+"),
]


def minute_bucket(minute: int | None) -> str:
    if minute is None:
        return "bilinmiyor"
    for lo, hi, label in MINUTE_BUCKETS:
        if lo <= minute < hi:
            return label
    return "bilinmiyor"


def score_bucket(home: int | None, away: int | None) -> str:
    h = home or 0
    a = away or 0
    if h == 0 and a == 0:
        return "0-0"
    if h == a:
        return "beraberlik"
    if h > a:
        return "ev onde"
    return "deplasman onde"


def _rows(db: Session):
    return db.execute(
        select(Prediction, PredictionOutcome, Match, League)
        .join(PredictionOutcome, PredictionOutcome.prediction_id == Prediction.id)
        .join(Match, Prediction.match_id == Match.id)
        .join(League, Match.league_id == League.id, isouter=True)
        .where(PredictionOutcome.actual.is_not(None))
    ).all()


def _segment(label_key: str, probs: list[float], outcomes: list[int], label: str) -> Segment:
    count = len(probs)
    if count == 0:
        return Segment(key=label_key, label=label, count=0, summary=None, note="Kayit yok")
    if count < MIN_SAMPLE_FOR_REPORT:
        return Segment(
            key=label_key,
            label=label,
            count=count,
            summary=None,
            note=f"Yetersiz ornek ({count} < {MIN_SAMPLE_FOR_REPORT}); performans yuzdesi yayinlanmaz.",
        )
    return Segment(key=label_key, label=label, count=count, summary=summarize(probs, outcomes))


def build_report(db: Session, dimension: str = "overall") -> list[Segment]:
    rows = _rows(db)
    groups: dict[tuple[str, str], list[tuple[float, int]]] = defaultdict(list)

    def key_label(pred: Prediction, match: Match, league: League | None) -> tuple[str, str]:
        if dimension == "target":
            return pred.target, pred.target
        if dimension == "league":
            name = league.name if league else "bilinmiyor"
            return match.league_id, name
        if dimension == "minute":
            b = minute_bucket(pred.minute_at_prediction)
            return b, b
        if dimension == "score":
            b = score_bucket(pred.score_home, pred.score_away)
            return b, b
        if dimension == "market":
            return pred.market, pred.market
        return "overall", "genel"

    for pred, outcome, match, league in rows:
        k, lab = key_label(pred, match, league)
        groups[(k, lab)].append((pred.probability, int(outcome.actual)))

    segments = [
        _segment(k, [p for p, _ in items], [o for _, o in items], lab)
        for (k, lab), items in sorted(groups.items())
    ]
    return segments


def report_to_api(segments: list[Segment]) -> list[dict]:
    return [
        {
            "key": s.key,
            "label": s.label,
            "count": s.count,
            "note": s.note,
            "metrics": None
            if s.summary is None
            else {
                "brier": s.summary.brier,
                "log_loss": s.summary.log_loss,
                "base_rate": s.summary.base_rate,
                "baseline_brier": s.summary.baseline_brier,
                "baseline_log_loss": s.summary.baseline_log_loss,
                "calibration": [
                    {
                        "low": b.low,
                        "high": b.high,
                        "count": b.count,
                        "avg_predicted": b.avg_predicted,
                        "actual_rate": b.actual_rate,
                    }
                    for b in s.summary.buckets
                ],
            },
        }
        for s in segments
    ]
