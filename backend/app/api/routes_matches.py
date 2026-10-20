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
from app.services.match_view import key_markets, serialize_match
from app.services.odds import OddsService, odds_for_match
from app.timeutil import in_day
from app.services.prediction_service import persist_predictions, run_models
from app.services.prematch import PreviewTask, build_previews

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
    matches = _live_query(db)
    out = []
    for match in matches:
        league_obj = db.get(League, match.league_id)
        if league and league not in (match.league_id, league_obj.provider_league_id if league_obj else None):
            continue
        if minute_min is not None and (match.elapsed_minute or 0) < minute_min:
            continue
        if minute_max is not None and (match.elapsed_minute or 999) > minute_max:
            continue
        if data_quality and match.data_quality != data_quality:
            continue

        bundle = run_models(db, match)
        goal_keys = key_markets(bundle.goal)
        corner_keys = key_markets(bundle.corner)
        g10 = goal_keys.get("goal_next_10_min")
        c10 = corner_keys.get("corner_next_10_min")
        if min_goal_prob is not None and (g10 is None or g10 < min_goal_prob):
            continue
        if min_corner_prob is not None and (c10 is None or c10 < min_corner_prob):
            continue

        item = serialize_match(db, match, include_stats=True)
        item["predictions"] = {
            "goal_sufficient": bundle.goal.sufficient,
            "corner_sufficient": bundle.corner.sufficient,
            "goal_insufficient_reason": bundle.goal.insufficient_reason,
            "corner_insufficient_reason": bundle.corner.insufficient_reason,
            "goal_confidence": bundle.goal.confidence,
            "corner_confidence": bundle.corner.confidence,
            "goal": goal_keys,
            "corner": corner_keys,
            "source": "live",
            "as_of_minute": bundle.features.minute,
            "baseline": {
                "goal_source": bundle.baseline.source,
                "corner_source": bundle.baseline.source,
                "sample_matches": bundle.baseline.sample_matches,
                "note": bundle.baseline.note,
            },
        }
        out.append(item)

    out.sort(key=lambda x: x["minute"] or 0, reverse=True)
    return {"count": len(out), "matches": out}


def _prediction_payload(db: Session, match: Match) -> dict:
    if match.status_short in LIVE_SHORT_STATUSES:
        bundle = run_models(db, match)
        goal_keys = key_markets(bundle.goal)
        corner_keys = key_markets(bundle.corner)
        return {
            "goal_sufficient": bundle.goal.sufficient,
            "corner_sufficient": bundle.corner.sufficient,
            "goal_insufficient_reason": bundle.goal.insufficient_reason,
            "corner_insufficient_reason": bundle.corner.insufficient_reason,
            "goal_confidence": bundle.goal.confidence,
            "corner_confidence": bundle.corner.confidence,
            "goal": goal_keys,
            "corner": corner_keys,
            "source": "live",
            "as_of_minute": bundle.features.minute,
            "baseline": {
                "goal_source": bundle.baseline.source,
                "corner_source": bundle.baseline.source,
                "sample_matches": bundle.baseline.sample_matches,
                "note": bundle.baseline.note,
            },
        }
    if match.status_short not in NOT_STARTED:
        history = (
            db.query(Prediction)
            .filter(Prediction.match_id == match.id)
            .order_by(Prediction.created_at.desc())
            .all()
        )
        if history:
            def latest_map(target: str) -> tuple[dict[str, float], int | None]:
                target_rows = [r for r in history if r.target == target]
                if not target_rows:
                    return {}, None
                minute = max((r.minute_at_prediction or 0) for r in target_rows)
                rows = [r for r in target_rows if (r.minute_at_prediction or 0) == minute]
                return {r.market: r.probability for r in rows}, minute

            goal_map, goal_minute = latest_map("goal")
            corner_map, corner_minute = latest_map("corner")
            if goal_map or corner_map:
                minute = max(goal_minute or 0, corner_minute or 0)
                return {
                    "goal_sufficient": bool(goal_map),
                    "corner_sufficient": bool(corner_map),
                    "goal_insufficient_reason": None if goal_map else "Kayitli tahmin yok.",
                    "corner_insufficient_reason": None if corner_map else "Kayitli tahmin yok.",
                    "goal_confidence": 0.0,
                    "corner_confidence": 0.0,
                    "goal": goal_map,
                    "corner": corner_map,
                    "source": "history",
                    "as_of_minute": minute,
                    "baseline": {
                        "goal_source": "kayitli tahmin",
                        "corner_source": "kayitli tahmin",
                        "sample_matches": 0,
                        "note": f"Mac bitti; {minute}. dakikada kaydedilen tahminler gosteriliyor.",
                    },
                }

    reason = "Mac baslamadi; tahmin mac baslayinca uretilir." if match.status_short in NOT_STARTED else "Mac bitti; tahmin uretilmez."
    return {
        "goal_sufficient": False,
        "corner_sufficient": False,
        "goal_insufficient_reason": reason,
        "corner_insufficient_reason": reason,
        "goal_confidence": 0.0,
        "corner_confidence": 0.0,
        "goal": {},
        "corner": {},
        "source": "none",
        "as_of_minute": None,
        "baseline": {
            "goal_source": "—",
            "corner_source": "—",
            "sample_matches": 0,
            "note": reason,
        },
    }


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
    return {"refreshed": len(matches)}


@router.get("/matches/day")
def day_matches(
    date: str = Query(..., description="YYYY-MM-DD"),
    db: Session = Depends(get_db),
) -> dict:
    matches = db.execute(select(Match).order_by(Match.kickoff_at)).scalars().all()
    out = []
    for match in matches:
        if not in_day(match.kickoff_at, date):
            continue
        item = serialize_match(db, match, include_stats=True)
        item["predictions"] = _prediction_payload(db, match)
        out.append(item)
    out.sort(key=lambda x: x["kickoff_at"] or "")
    return {"count": len(out), "matches": out}


@router.get("/matches/previews")
def day_previews(
    date: str = Query(..., description="YYYY-MM-DD"),
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
            )
        )
    return {"count": len(tasks), "previews": build_previews(provider, tasks)}


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
    return {
        "match": serialize_match(db, match, include_stats=True),
        "predictions_created": created,
        "current_predictions": bundle.to_api(),
    }


@router.post("/matches/enrich-watchlist")
def enrich_watchlist(
    db: Session = Depends(get_db),
    ingest: LiveIngestService = Depends(get_ingest_dep),
    limit: int = Query(3, ge=1, le=20),
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
    return {"processed": len(results), "results": results}
