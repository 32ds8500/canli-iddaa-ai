"""Tahmin uretimi ve kalici kayit servisi."""
from __future__ import annotations

import json
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.engines.baselines import Baseline, get_baseline
from app.engines.corner_model import CornerModel
from app.engines.features import MatchFeatures, compute_features
from app.engines.goal_model import GoalModel
from app.engines.types import EngineResult
from app.models import Match, Prediction

FINISHED_STATUSES = {"FT", "AET", "PEN", "FINISHED"}

_goal_model = GoalModel()
_corner_model = CornerModel()


@dataclass
class MatchPredictionBundle:
    match_id: str
    features: MatchFeatures
    baseline: Baseline
    goal: EngineResult
    corner: EngineResult

    def to_api(self) -> dict:
        return {
            "match_id": self.match_id,
            "minute": self.features.minute,
            "remaining_minutes": self.features.remaining_minutes,
            "score": {"home": self.features.score_home, "away": self.features.score_away},
            "data_quality": self.features.data_quality,
            "data_age_seconds": self.features.data_age_seconds,
            "baseline": {
                "source": self.baseline.source,
                "sample_matches": self.baseline.sample_matches,
                "note": self.baseline.note,
            },
            "goal": _engine_to_api(self.goal),
            "corner": _engine_to_api(self.corner),
        }


def _engine_to_api(result: EngineResult) -> dict:
    return {
        "target": result.target,
        "model": {"name": result.model_name, "version": result.model_version},
        "sufficient": result.sufficient,
        "insufficient_reason": result.insufficient_reason,
        "confidence": result.confidence,
        "factors": result.factors,
        "expected": result.expected,
        "predictions": [
            {
                "market": p.market,
                "probability": p.probability,
                "horizon_minutes": p.horizon_minutes,
                "threshold": p.threshold,
                "rationale": p.rationale,
            }
            for p in result.predictions
        ],
    }


def run_models(db: Session, match: Match) -> MatchPredictionBundle:
    feats = compute_features(db, match)
    baseline = get_baseline(db, match.provider, feats.league_provider_id)
    goal = _goal_model.run(feats, baseline)
    corner = _corner_model.run(feats, baseline)
    return MatchPredictionBundle(
        match_id=match.id, features=feats, baseline=baseline, goal=goal, corner=corner
    )


def persist_predictions(
    db: Session,
    bundle: MatchPredictionBundle,
    provider: str,
    *,
    match_status: str | None = None,
) -> int:
    """Yeterli olan tahminleri zaman damgasi ve model surumuyle kaydeder.

    Ayni mac/dakika/market icin ayni model surumu zaten kayitliysa tekrar yazmaz;
    boylece sürüm gecmisi korunur ve mukerrer kayit olusmaz.

    Bitmis maclar icin tahmin kaydedilmez: sonucu bilinen bir macta uretilen
    olasilik gecmis performans olarak sunulamaz (veri sizintisi olur).
    """
    if match_status in FINISHED_STATUSES:
        return 0
    created = 0
    feats = bundle.features
    for result in (bundle.goal, bundle.corner):
        if not result.sufficient:
            continue
        for p in result.predictions:
            exists = (
                db.query(Prediction)
                .filter(
                    Prediction.match_id == bundle.match_id,
                    Prediction.market == p.market,
                    Prediction.model_version == result.model_version,
                    Prediction.minute_at_prediction == feats.minute,
                )
                .first()
            )
            if exists:
                continue
            db.add(
                Prediction(
                    match_id=bundle.match_id,
                    minute_at_prediction=feats.minute,
                    score_home=feats.score_home,
                    score_away=feats.score_away,
                    target=result.target,
                    market=p.market,
                    horizon_minutes=p.horizon_minutes,
                    threshold=p.threshold,
                    probability=p.probability,
                    model_name=result.model_name,
                    model_version=result.model_version,
                    data_quality=feats.data_quality,
                    confidence=result.confidence,
                    provider=provider,
                    data_age_seconds=feats.data_age_seconds,
                    features_json=json.dumps(
                        {"pressure_home": feats.pressure_home, "pressure_away": feats.pressure_away},
                        ensure_ascii=False,
                    ),
                    rationale=p.rationale,
                )
            )
            created += 1
    if created:
        db.commit()
    return created
