"""Gol olasiligi motoru (istatistiksel temel model).

Zamana bagli Poisson sureci + lig/takim baseline + mac ici basinc ayarlari.
Tek bir istatistige dayanmaz; sut, isabetli sut, tehlikeli atak, sahip olma
(YALNIZCA yardimci, tek basina degil), kirmizi kart ve skor durumu birlikte
kullanilir. xG verisi varsa ayri faktor olarak raporlanir.
"""
from __future__ import annotations

import math

from app.engines.baselines import Baseline
from app.engines.confidence import assess
from app.engines.features import MatchFeatures
from app.engines.math_utils import clamp, poisson_sf, prob_at_least_one
from app.engines.types import EngineResult, MarketPrediction

MODEL_NAME = "goal-time-poisson"
MODEL_VERSION = "1.0.0"

GOAL_THRESHOLDS = (1.5, 2.5, 3.5, 4.5)
HORIZONS = (5, 10, 15)


def _time_weight(minute: float) -> float:
    """Gol yogunlugunun dakikaya gore carpani (0..90, ortalama ~1.0)."""
    m = clamp(minute, 0.0, 90.0)
    return 0.7 + 0.6 * (m / 90.0)


def _weighted_minutes(start: float, end: float) -> float:
    start = clamp(start, 0.0, 90.0)
    end = clamp(end, 0.0, 90.0)
    if end <= start:
        return 0.0
    return (end - start) * ((_time_weight(start) + _time_weight(end)) / 2.0)


def _attack_factors(feats: MatchFeatures) -> tuple[float, float, list[str]]:
    hf = af = 1.0
    factors: list[str] = []

    w10 = feats.windows.get("last_10", {})
    h, a = w10.get("home"), w10.get("away")
    if (h and h.available) or (a and a.available):
        so_h = (h.shots_on or 0) if h else 0
        so_a = (a.shots_on or 0) if a else 0
        da_h = (h.dangerous_attacks or 0) if h else 0
        da_a = (a.dangerous_attacks or 0) if a else 0
        adj = clamp(0.08 * (so_h - so_a) + 0.01 * (da_h - da_a), -0.4, 0.4)
        hf *= 1 + adj
        af *= 1 - adj
        factors.append(
            f"Son 10 dk: isabetli sut ev {so_h}-{so_a} dep, tehlikeli atak {da_h}-{da_a}"
        )

    if feats.home_possession is not None and feats.away_possession is not None:
        pos_adj = clamp((feats.home_possession - 50) * 0.002, -0.06, 0.06)
        hf *= 1 + pos_adj
        af *= 1 - pos_adj
        factors.append(
            f"Topa sahip olma ev {feats.home_possession}% / dep {feats.away_possession}% "
            "(yardimci faktor; tek basina belirleyici degil)"
        )

    if feats.home_red_cards > 0:
        hf *= 0.75
        af *= 1.2
        factors.append(f"Ev sahibinde {feats.home_red_cards} kirmizi kart (baskiyi dusurur)")
    if feats.away_red_cards > 0:
        af *= 0.75
        hf *= 1.2
        factors.append(f"Deplasmanda {feats.away_red_cards} kirmizi kart (baskiyi dusurur)")

    # Skor durumuna gore taktik/risk
    if feats.minute >= 60:
        if feats.goal_diff <= -1:
            hf *= 1.12
            factors.append("Ev sahibi geride ve gec dakika: risk artisi (gol atma egilimi +)")
        if feats.goal_diff >= 1:
            af *= 1.12
            factors.append("Deplasman geride ve gec dakika: risk artisi (gol atma egilimi +)")
    if feats.minute >= 70:
        if feats.goal_diff >= 2:
            hf *= 0.92
            factors.append("Ev sahibi 2+ farkli onde: tempo dusme egilimi")
        if feats.goal_diff <= -2:
            af *= 0.92
            factors.append("Deplasman 2+ farkli onde: tempo dusme egilimi")

    return clamp(hf, 0.4, 2.2), clamp(af, 0.4, 2.2), factors


class GoalModel:
    name = MODEL_NAME
    version = MODEL_VERSION

    def run(self, feats: MatchFeatures, baseline: Baseline) -> EngineResult:
        assessment = assess(feats)
        result = EngineResult(
            target="goal",
            model_name=self.name,
            model_version=self.version,
            confidence=assessment.confidence,
            sufficient=assessment.sufficient,
            insufficient_reason=assessment.reason,
        )
        if not assessment.sufficient:
            return result

        hf, af, factors = _attack_factors(feats)
        result.factors = factors

        # Baseline ev/deplasman gol oranlari (dakika basina)
        base = baseline
        lambda_home = base.goals_per_match * base.goals_home_share / 90.0 * hf
        lambda_away = base.goals_per_match * (1 - base.goals_home_share) / 90.0 * af
        lambda_total = lambda_home + lambda_away

        result.factors.append(
            f"Taban cizgi ({base.source}): mac basi {base.goals_per_match:.2f} gol, ev payi {base.goals_home_share:.2f}"
        )
        result.factors.append(
            f"Dakika-basi gol orani: ev {lambda_home:.4f}, dep {lambda_away:.4f} (carpan ev {hf:.2f}/dep {af:.2f})"
        )

        # --- Kisa ufuklar: en az bir gol / takim golu ---
        for horizon in HORIZONS:
            eff = _weighted_minutes(feats.minute, feats.minute + horizon)
            p_any = prob_at_least_one(lambda_total, eff)
            p_home = prob_at_least_one(lambda_home, eff)
            p_away = prob_at_least_one(lambda_away, eff)
            result.predictions.append(
                MarketPrediction(
                    market=f"goal_next_{horizon}_min",
                    probability=round(p_any, 4),
                    horizon_minutes=horizon,
                    threshold=None,
                    rationale=f"Onumuzdeki {horizon} dk en az bir gol (Poisson).",
                )
            )
            result.predictions.append(
                MarketPrediction(
                    market=f"goal_home_next_{horizon}_min",
                    probability=round(p_home, 4),
                    horizon_minutes=horizon,
                    threshold=None,
                    rationale=f"Onumuzdeki {horizon} dk ev sahibi gol (Poisson).",
                )
            )
            result.predictions.append(
                MarketPrediction(
                    market=f"goal_away_next_{horizon}_min",
                    probability=round(p_away, 4),
                    horizon_minutes=horizon,
                    threshold=None,
                    rationale=f"Onumuzdeki {horizon} dk deplasman gol (Poisson).",
                )
            )

        # --- Macin kalani ---
        eff_rest = _weighted_minutes(feats.minute, 90)
        p_rest_any = prob_at_least_one(lambda_total, eff_rest)
        result.predictions.append(
            MarketPrediction(
                market="goal_rest_at_least_one",
                probability=round(p_rest_any, 4),
                horizon_minutes=feats.remaining_minutes,
                threshold=None,
                rationale="Macin kalan suresinde en az bir gol.",
            )
        )
        result.predictions.append(
            MarketPrediction(
                market="goal_home_rest",
                probability=round(prob_at_least_one(lambda_home, eff_rest), 4),
                horizon_minutes=feats.remaining_minutes,
                threshold=None,
                rationale="Ev sahibinin macin kalaninda gol atmasi.",
            )
        )
        result.predictions.append(
            MarketPrediction(
                market="goal_away_rest",
                probability=round(prob_at_least_one(lambda_away, eff_rest), 4),
                horizon_minutes=feats.remaining_minutes,
                threshold=None,
                rationale="Deplasmanin macin kalaninda gol atmasi.",
            )
        )

        # --- Siradaki gol ---
        if lambda_total > 0:
            next_home = lambda_home / lambda_total
        else:
            next_home = 0.5
        result.predictions.append(
            MarketPrediction(
                market="goal_next_home",
                probability=round(next_home, 4),
                horizon_minutes=feats.remaining_minutes,
                threshold=None,
                rationale="Bir sonraki golun ev sahibi tarafindan atilmasi.",
            )
        )
        result.predictions.append(
            MarketPrediction(
                market="goal_next_away",
                probability=round(1 - next_home, 4),
                horizon_minutes=feats.remaining_minutes,
                threshold=None,
                rationale="Bir sonraki golun deplasman tarafindan atilmasi.",
            )
        )

        # --- Toplam gol esikleri (mac sonu) ---
        mean_rest = lambda_total * eff_rest
        current = feats.total_goals
        for th in GOAL_THRESHOLDS:
            k = int(math.floor(th - current))
            p = poisson_sf(k, mean_rest) if mean_rest > 0 else (1.0 if current > th else 0.0)
            result.predictions.append(
                MarketPrediction(
                    market=f"goals_total_over_{str(th).replace('.', '_')}",
                    probability=round(p, 4),
                    horizon_minutes=feats.remaining_minutes,
                    threshold=th,
                    rationale=f"Mac sonu toplam gol {th} ustu.",
                )
            )

        return result
