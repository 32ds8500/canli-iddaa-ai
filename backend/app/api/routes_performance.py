"""Tahmin gecmisi ve performans endpoint'leri."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.eval.report import build_report, report_to_api
from app.eval.settlement import settle_finished_matches
from app.models import Prediction, PredictionOutcome

router = APIRouter(prefix="/api", tags=["predictions"])


@router.get("/predictions")
def list_predictions(
    db: Session = Depends(get_db),
    match_id: str | None = Query(None),
    target: str | None = Query(None, description="goal|corner"),
    only_settled: bool = Query(False),
    limit: int = Query(200, ge=1, le=2000),
) -> dict:
    stmt = (
        select(Prediction, PredictionOutcome)
        .outerjoin(PredictionOutcome, PredictionOutcome.prediction_id == Prediction.id)
        .order_by(Prediction.created_at.desc())
        .limit(limit)
    )
    if match_id:
        stmt = stmt.where(Prediction.match_id == match_id)
    if target:
        stmt = stmt.where(Prediction.target == target)
    rows = db.execute(stmt).all()
    items = []
    for p, o in rows:
        if only_settled and (o is None or o.actual is None):
            continue
        items.append(
            {
                "id": p.id,
                "match_id": p.match_id,
                "created_at": p.created_at.isoformat(),
                "minute": p.minute_at_prediction,
                "score": {"home": p.score_home, "away": p.score_away},
                "target": p.target,
                "market": p.market,
                "horizon_minutes": p.horizon_minutes,
                "threshold": p.threshold,
                "probability": p.probability,
                "model": {"name": p.model_name, "version": p.model_version},
                "confidence": p.confidence,
                "data_quality": p.data_quality,
                "provider": p.provider,
                "data_age_seconds": p.data_age_seconds,
                "rationale": p.rationale,
                "outcome": None
                if o is None
                else {
                    "actual": o.actual,
                    "status": o.evaluation_status,
                    "detail": o.actual_detail,
                    "resolved_at": o.resolved_at.isoformat(),
                },
            }
        )
    return {"count": len(items), "predictions": items}


@router.get("/performance")
def performance(
    db: Session = Depends(get_db),
    dimension: str = Query("overall", pattern="^(overall|target|league|minute|score|market)$"),
) -> dict:
    segments = build_report(db, dimension=dimension)
    return {
        "dimension": dimension,
        "min_sample_for_percentage": 30,
        "note": (
            "Yeterli ornek olmayan segmentlerde performans yuzdesi yayinlanmaz. "
            "Olasilik, kesinlik veya para kazanma garantisi DEGILDIR."
        ),
        "segments": report_to_api(segments),
    }


@router.post("/performance/settle")
def settle(db: Session = Depends(get_db)) -> dict:
    updated = settle_finished_matches(db)
    return {"settled": updated}
