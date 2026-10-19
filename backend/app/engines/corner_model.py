"""Korner olasiligi motoru (gol modelinden BAGIMSIZ).

Kornerler kumelenebilir (kisa surede art arda gelebilir); bu nedenle gecmis
kisa sureli korner patlamasi gelecek korner icin KESIN kanit sayilmaz.
Model, kayan pencere korner/sut/tehlikeli atak sinyallerini ve mac durumunu
birlikte kullanir.
"""
from __future__ import annotations

import math

from app.engines.baselines import Baseline
from app.engines.confidence import assess
from app.engines.features import MatchFeatures
from app.engines.math_utils import clamp, poisson_sf, prob_at_least_one
from app.engines.types import EngineResult, MarketPrediction

MODEL_NAME = "corner-time-poisson"
MODEL_VERSION = "1.0.0"

CORNER_THRESHOLDS = (7.5, 8.5, 9.5, 10.5)
TEAM_CORNER_THRESHOLDS = (4.5, 5.5)
HORIZONS = (5, 10, 15)


def _time_weight(minute: float) -> float:
    m = clamp(minute, 0.0, 90.0)
    # Korner yogunlugu gec oyunda bir miktar artar (goldan daha az)
    return 0.8 + 0.4 * (m / 90.0)


def _weighted_minutes(start: float, end: float) -> float:
    start = clamp(start, 0.0, 90.0)
    end = clamp(end, 0.0, 90.0)
    if end <= start:
        return 0.0
    return (end - start) * ((_time_weight(start) + _time_weight(end)) / 2.0)


def _corner_factors(feats: MatchFeatures) -> tuple[float, float, list[str]]:
    hf = af = 1.0
    factors: list[str] = []

    w10 = feats.windows.get("last_10", {})
    h, a = w10.get("home"), w10.get("away")
    if (h and h.available) or (a and a.available):
        c_h = (h.corners or 0) if h else 0
        c_a = (a.corners or 0) if a else 0
        s_h = (h.shots or 0) if h else 0
        s_a = (a.shots or 0) if a else 0
        da_h = (h.dangerous_attacks or 0) if h else 0
        da_a = (a.dangerous_attacks or 0) if a else 0
        adj = clamp(0.10 * (c_h - c_a) + 0.03 * (s_h - s_a) + 0.01 * (da_h - da_a), -0.45, 0.45)
        hf *= 1 + adj
        af *= 1 - adj
        factors.append(
            f"Son 10 dk: korner ev {c_h}-{c_a} dep, sut {s_h}-{s_a}, tehlikeli atak {da_h}-{da_a}"
        )
        if (c_h + c_a) >= 3:
            factors.append(
                "Son 10 dk korner kumelenmesi var; kumelenme gelecek icin KESIN gosterge degildir."
            )

    if feats.home_possession is not None and feats.away_possession is not None:
        pos_adj = clamp((feats.home_possession - 50) * 0.002, -0.06, 0.06)
        hf *= 1 + pos_adj
        af *= 1 - pos_adj
        factors.append(
            f"Topa sahip olma ev {feats.home_possession}% / dep {feats.away_possession}% (yardimci)"
        )

    if feats.home_red_cards > 0:
        hf *= 0.8
        af *= 1.15
        factors.append("Ev sahibinde kirmizi kart: korner uretimi dusebilir")
    if feats.away_red_cards > 0:
        af *= 0.8
        hf *= 1.15
        factors.append("Deplasmanda kirmizi kart: korner uretimi dusebilir")

    if feats.minute >= 60:
        if feats.goal_diff <= -1:
            hf *= 1.15
            factors.append("Ev sahibi geride, gec dakika: kanat baskisi/korner egilimi +")
        if feats.goal_diff >= 1:
            af *= 1.15
            factors.append("Deplasman geride, gec dakika: kanat baskisi/korner egilimi +")

    return clamp(hf, 0.4, 2.3), clamp(af, 0.4, 2.3), factors


class CornerModel:
    name = MODEL_NAME
    version = MODEL_VERSION

    def run(self, feats: MatchFeatures, baseline: Baseline) -> EngineResult:
        assessment = assess(feats)
        result = EngineResult(
            target="corner",
            model_name=self.name,
            model_version=self.version,
            confidence=assessment.confidence,
            sufficient=assessment.sufficient,
            insufficient_reason=assessment.reason,
        )
        if not assessment.sufficient:
            return result

        hf, af, factors = _corner_factors(feats)
        result.factors = factors

        lambda_home = baseline.corners_per_match * baseline.corners_home_share / 90.0 * hf
        lambda_away = baseline.corners_per_match * (1 - baseline.corners_home_share) / 90.0 * af
        lambda_total = lambda_home + lambda_away

        result.factors.append(
            f"Taban cizgi ({baseline.source}): mac basi {baseline.corners_per_match:.2f} korner, "
            f"ev payi {baseline.corners_home_share:.2f}"
        )
        result.factors.append(
            f"Dakika-basi korner orani: ev {lambda_home:.4f}, dep {lambda_away:.4f}"
        )

        # Mevcut kumulatif korner (varsa)
        current_total = feats.current_corners_home + feats.current_corners_away

        # --- Kisa ufuklar ---
        for horizon in HORIZONS:
            eff = _weighted_minutes(feats.minute, feats.minute + horizon)
            result.predictions.append(
                MarketPrediction(
                    market=f"corner_next_{horizon}_min",
                    probability=round(prob_at_least_one(lambda_total, eff), 4),
                    horizon_minutes=horizon,
                    threshold=None,
                    rationale=f"Onumuzdeki {horizon} dk en az bir korner.",
                )
            )

        eff_rest = _weighted_minutes(feats.minute, 90)
        result.predictions.append(
            MarketPrediction(
                market="corner_rest_at_least_one",
                probability=round(prob_at_least_one(lambda_total, eff_rest), 4),
                horizon_minutes=feats.remaining_minutes,
                threshold=None,
                rationale="Macin kalaninda en az bir korner.",
            )
        )

        # Beklentiler (olasilik degil)
        exp_rest = lambda_total * eff_rest
        exp_home_rest = lambda_home * eff_rest
        exp_away_rest = lambda_away * eff_rest
        mean_rest = exp_rest
        result.expected = {
            "corner_expected_rest_total": round(exp_rest, 3),
            "corner_expected_rest_home": round(exp_home_rest, 3),
            "corner_expected_rest_away": round(exp_away_rest, 3),
            "corner_expected_match_total": round(current_total + exp_rest, 3),
            "corner_expected_match_home": round(feats.current_corners_home + exp_home_rest, 3),
            "corner_expected_match_away": round(feats.current_corners_away + exp_away_rest, 3),
        }

        # --- Toplam korner esikleri (mac sonu) ---
        for th in CORNER_THRESHOLDS:
            k = int(math.floor(th - current_total))
            p = poisson_sf(k, mean_rest) if mean_rest > 0 else (1.0 if current_total > th else 0.0)
            result.predictions.append(
                MarketPrediction(
                    market=f"corners_total_over_{str(th).replace('.', '_')}",
                    probability=round(p, 4),
                    horizon_minutes=feats.remaining_minutes,
                    threshold=th,
                    rationale=f"Mac sonu toplam korner {th} ustu.",
                )
            )

        # --- Takim bazli esikler ---
        for th in TEAM_CORNER_THRESHOLDS:
            kh = int(math.floor(th - feats.current_corners_home))
            ph = poisson_sf(kh, exp_home_rest) if exp_home_rest > 0 else (1.0 if feats.current_corners_home > th else 0.0)
            ka = int(math.floor(th - feats.current_corners_away))
            pa = poisson_sf(ka, exp_away_rest) if exp_away_rest > 0 else (1.0 if feats.current_corners_away > th else 0.0)
            result.predictions.append(
                MarketPrediction(
                    market=f"corners_home_over_{str(th).replace('.', '_')}",
                    probability=round(ph, 4),
                    horizon_minutes=feats.remaining_minutes,
                    threshold=th,
                    rationale=f"Ev sahibi mac sonu toplam korner {th} ustu.",
                )
            )
            result.predictions.append(
                MarketPrediction(
                    market=f"corners_away_over_{str(th).replace('.', '_')}",
                    probability=round(pa, 4),
                    horizon_minutes=feats.remaining_minutes,
                    threshold=th,
                    rationale=f"Deplasman mac sonu toplam korner {th} ustu.",
                )
            )

        # --- Siradaki korner ---
        if lambda_total > 0:
            next_home = lambda_home / lambda_total
        else:
            next_home = 0.5
        result.predictions.append(
            MarketPrediction(
                market="corner_next_home",
                probability=round(next_home, 4),
                horizon_minutes=feats.remaining_minutes,
                threshold=None,
                rationale="Bir sonraki kornerin ev sahibi tarafindan kazanilmasi.",
            )
        )
        result.predictions.append(
            MarketPrediction(
                market="corner_next_away",
                probability=round(1 - next_home, 4),
                horizon_minutes=feats.remaining_minutes,
                threshold=None,
                rationale="Bir sonraki kornerin deplasman tarafindan kazanilmasi.",
            )
        )

        return result

