"""Guven puani ve yeterlilik karari.

ONEMLI: Olasilik ile guven puani AYRI seylerdir. Yuzde 70 olasilik, yuzde 70
guven anlamina gelmez. Guven puani; veri kalitesi, veri tazeligi, taban
cizginin kaynagi (prior/estimated) ve kayan pencere kapsamindan turetilir.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.engines.features import MatchFeatures


@dataclass
class ConfidenceAssessment:
    confidence: float
    sufficient: bool
    reason: str | None


def _available_window_count(feats: MatchFeatures) -> int:
    count = 0
    for side_map in feats.windows.values():
        for tw in side_map.values():
            if tw.available:
                count += 1
    return count


def assess(feats: MatchFeatures) -> ConfidenceAssessment:
    if not feats.has_live_stats:
        return ConfidenceAssessment(
            confidence=0.2,
            sufficient=False,
            reason="Canli istatistik verisi saglayicidan alinamadi; tahmin uretilmedi.",
        )

    score = 0.5
    if feats.baseline_source == "estimated":
        score += 0.2
    else:
        score -= 0.05

    score += {"good": 0.15, "partial": -0.05, "conflicting": -0.2, "missing": -0.3,
              "unknown": -0.15}.get(feats.data_quality, -0.1)

    if feats.data_age_seconds is not None:
        if feats.data_age_seconds > 300:
            score -= 0.2
        elif feats.data_age_seconds > 180:
            score -= 0.1

    score += 0.02 * _available_window_count(feats)
    confidence = max(0.0, min(1.0, round(score, 3)))

    sufficient = True
    reason: str | None = None
    if feats.data_quality in ("missing", "unknown"):
        sufficient = False
        reason = "Veri kalitesi yetersiz (eksik/bilinmiyor); tahmin uretilmedi."
    elif feats.minute >= 10 and feats.data_quality == "partial" and _available_window_count(feats) == 0:
        sufficient = False
        reason = "Kayan pencere verisi yok; guvenilir canli tahmin uretilemedi."

    return ConfidenceAssessment(confidence=confidence, sufficient=sufficient, reason=reason)
