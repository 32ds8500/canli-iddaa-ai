"""Mac ve lig endpoint'leri."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_ingest_dep, get_provider_dep
from app.db import get_db
from app.eval.settlement import settle_match
from app.ingest.live import LIVE_SHORT_STATUSES, NOT_STARTED, LiveIngestService
from app.models import League, Match, MatchEvent, Prediction, PredictionOutcome, StatSnapshot, Team
from app.providers.base import FootballProvider, ProviderError
from app.services.match_view import serialize_match
from app.services.payloads import _prediction_payload, build_day, build_live, day_cache_key, live_cache_key
from app.services.response_cache import cached, invalidate
from app.services.odds import OddsService, odds_for_match
from app.timeutil import in_day
from app.services.prediction_service import persist_predictions, run_models
from app.services.prematch import PreviewTask, build_preview, build_previews

router = APIRouter(prefix="/api", tags=["matches"])


@router.get("/leagues")
def list_leagues(db: Session = Depends(get_db)) -> dict:
    leagues = db.execute(select(League).order_by(League.name)).scalars().all()
    return {
        "leagues": [
            {
                "id": lg.id,
                "provider_league_id": lg.provider_league_id,
                "name": lg.name,
                "country": lg.country,
                "kind": lg.kind,
                "current_season": lg.current_season,
                "coverage": {
                    "live_stats": lg.cov_live_stats,
                    "corners": lg.cov_corners,
                    "dangerous_attacks": lg.cov_dangerous_attacks,
                    "xg": lg.cov_xg,
                },
                "coverage_notes": lg.coverage_notes,
                "verified_at": lg.verified_at.isoformat() if lg.verified_at else None,
            }
            for lg in leagues
        ]
    }


@router.post("/matches/refresh-live")
def refresh_live(
    db: Session = Depends(get_db), ingest: LiveIngestService = Depends(get_ingest_dep)
) -> dict:
    try:
        matches = ingest.refresh_live(db)
    except ProviderError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    invalidate("live:")
    invalidate("day:")
    return {"refreshed": len(matches), "matches": [serialize_match(db, m, include_stats=False) for m in matches]}


def _live_query(db: Session):
    return db.execute(
        select(Match).where(Match.status_short.in_(list(LIVE_SHORT_STATUSES)))
    ).scalars().all()


@router.get("/matches/live")
def live_matches(
    db: Session = Depends(get_db),
    league: str | None = Query(None, description="league id (provider:xxx) veya provider_league_id"),
    minute_min: int | None = Query(None),
    minute_max: int | None = Query(None),
    min_goal_prob: float | None = Query(None, description="goal_next_10_min esigi"),
    min_corner_prob: float | None = Query(None, description="corner_next_10_min esigi"),
    data_quality: str | None = Query(None),
) -> dict:
    key = live_cache_key(league, minute_min, minute_max, min_goal_prob, min_corner_prob, data_quality)
    return cached(
        key,
        150.0,
        lambda: build_live(
            db,
            league=league,
            minute_min=minute_min,
            minute_max=minute_max,
            min_goal_prob=min_goal_prob,
            min_corner_prob=min_corner_prob,
            data_quality=data_quality,
        ),
    )


@router.post("/matches/refresh-day")
def refresh_day(
    date: str = Query(..., description="YYYY-MM-DD"),
    db: Session = Depends(get_db),
    ingest: LiveIngestService = Depends(get_ingest_dep),
) -> dict:
    try:
        matches = ingest.refresh_day(db, date)
    except ProviderError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    invalidate("day:")
    invalidate("live:")
    return {"refreshed": len(matches)}


@router.get("/matches/day")
def day_matches(
    date: str = Query(..., description="YYYY-MM-DD"),
    db: Session = Depends(get_db),
) -> dict:
    return cached(day_cache_key(date), 150.0, lambda: build_day(db, date))


@router.get("/matches/previews")
def day_previews(
    date: str = Query(..., description="YYYY-MM-DD"),
    limit: int = Query(12, ge=1, le=60, description="En fazla kac mac icin onizleme"),
    db: Session = Depends(get_db),
    provider: FootballProvider = Depends(get_provider_dep),
) -> dict:
    """Gunu henuz baslamamis maclari icin form/H2H ve mac oncesi tahmin."""
    matches = db.execute(select(Match).order_by(Match.kickoff_at)).scalars().all()
    tasks: list[PreviewTask] = []
    for match in matches:
        if match.status_short not in NOT_STARTED:
            continue
        if not in_day(match.kickoff_at, date):
            continue
        home = db.get(Team, match.home_team_id)
        away = db.get(Team, match.away_team_id)
        tasks.append(
            PreviewTask(
                match_id=match.id,
                home_id=match.home_team_id.split(":", 1)[-1],
                away_id=match.away_team_id.split(":", 1)[-1],
                home_name=home.name if home else "",
                away_name=away.name if away else "",
                provider_fixture_id=match.provider_fixture_id,
                kickoff_at=match.kickoff_at.isoformat() if match.kickoff_at else None,
            )
        )
    tasks.sort(key=lambda t: t.kickoff_at or "")
    return {"count": len(tasks), "previews": build_previews(provider, tasks[:limit])}


@router.get("/matches/{match_id}/preview")
def match_preview(
    match_id: str,
    db: Session = Depends(get_db),
    provider: FootballProvider = Depends(get_provider_dep),
) -> dict:
    match = db.get(Match, match_id)
    if match is None:
        raise HTTPException(status_code=404, detail="Mac bulunamadi")
    home = db.get(Team, match.home_team_id)
    away = db.get(Team, match.away_team_id)
    preview = build_preview(
        provider,
        match.home_team_id.split(":", 1)[-1],
        match.away_team_id.split(":", 1)[-1],
        home.name if home else "",
        away.name if away else "",
        match.provider_fixture_id,
    )
    return {"match_id": match.id, "preview": preview}


@router.post("/odds/refresh")
def refresh_odds(db: Session = Depends(get_db)) -> dict:
    service = OddsService()
    if not service.is_configured():
        raise HTTPException(status_code=503, detail="Oran kaynagi yapilandirilmamis (ODDS_API_KEY).")
    stored = service.refresh(db)
    return {"stored": stored}


@router.get("/matches/{match_id}")
def match_detail(match_id: str, db: Session = Depends(get_db)) -> dict:
    match = db.get(Match, match_id)
    if match is None:
        raise HTTPException(status_code=404, detail="Mac bulunamadi")
    data = serialize_match(db, match, include_stats=True)
    data["odds"] = odds_for_match(db, match.id)

    events = db.execute(
        select(MatchEvent).where(MatchEvent.match_id == match.id).order_by(MatchEvent.minute)
    ).scalars().all()
    data["events"] = [
        {
            "minute": e.minute,
            "extra": e.extra_minute,
            "type": e.type,
            "detail": e.detail,
            "side": e.side,
            "player": e.player,
            "assist": e.assist,
        }
        for e in events
    ]

    snaps = db.execute(
        select(StatSnapshot).where(StatSnapshot.match_id == match.id).order_by(StatSnapshot.minute)
    ).scalars().all()
    data["timeline"] = [
        {
            "minute": s.minute,
            "side": s.side,
            "shots": s.shots_total,
            "shots_on": s.shots_on,
            "corners": s.corners,
            "dangerous_attacks": s.dangerous_attacks,
            "xg": s.xg,
            "fired_at": s.fired_at.isoformat() if s.fired_at else None,
        }
        for s in snaps
    ]

    bundle = run_models(db, match)
    data["current_predictions"] = bundle.to_api()

    hist = db.execute(
        select(Prediction, PredictionOutcome)
        .outerjoin(PredictionOutcome, PredictionOutcome.prediction_id == Prediction.id)
        .where(Prediction.match_id == match.id)
        .order_by(Prediction.created_at.desc())
        .limit(300)
    ).all()
    data["prediction_history"] = [
        {
            "id": p.id,
            "created_at": p.created_at.isoformat(),
            "minute": p.minute_at_prediction,
            "score": {"home": p.score_home, "away": p.score_away},
            "target": p.target,
            "market": p.market,
            "probability": p.probability,
            "model": {"name": p.model_name, "version": p.model_version},
            "confidence": p.confidence,
            "data_quality": p.data_quality,
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
        for p, o in hist
    ]
    return data


@router.post("/matches/{match_id}/refresh")
def refresh_match(
    match_id: str,
    db: Session = Depends(get_db),
    ingest: LiveIngestService = Depends(get_ingest_dep),
) -> dict:
    match = db.get(Match, match_id)
    if match is None:
        raise HTTPException(status_code=404, detail="Mac bulunamadi")
    try:
        ingest.enrich_match(db, match)
    except ProviderError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    bundle = run_models(db, match)
    created = persist_predictions(db, bundle, provider=match.provider, match_status=match.status_short)
    settle_match(db, match)
    invalidate("live:")
    invalidate("day:")
    return {
        "match": serialize_match(db, match, include_stats=True),
        "predictions_created": created,
        "current_predictions": bundle.to_api(),
    }


@router.post("/matches/enrich-watchlist")
def enrich_watchlist(
    db: Session = Depends(get_db),
    ingest: LiveIngestService = Depends(get_ingest_dep),
    limit: int = Query(3, ge=1, le=200),
) -> dict:
    """Canli maclardan en onemli N tanesi icin istatistik ceker (kota dostu)."""
    matches = _live_query(db)
    matches.sort(key=lambda m: (m.elapsed_minute or 0), reverse=True)
    results = []
    for match in matches[:limit]:
        try:
            ingest.enrich_match(db, match)
            bundle = run_models(db, match)
            created = persist_predictions(db, bundle, provider=match.provider, match_status=match.status_short)
            settle_match(db, match)
            results.append({"match_id": match.id, "predictions_created": created, "ok": True})
        except ProviderError as exc:
            results.append({"match_id": match.id, "ok": False, "error": str(exc)})
    invalidate("live:")
    invalidate("day:")
    return {"processed": len(results), "results": results}
