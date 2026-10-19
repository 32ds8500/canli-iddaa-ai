"""Sistem durumu, saglayici ve kota bilgisi."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_provider_dep
from app.config import get_settings
from app.db import get_db
from app.models import League, Match, Prediction, PredictionOutcome
from app.providers import TARGET_COMPETITIONS
from app.providers.base import FootballProvider

router = APIRouter(prefix="/api/system", tags=["system"])


@router.get("/status")
def status(db: Session = Depends(get_db), provider: FootballProvider = Depends(get_provider_dep)) -> dict:
    settings = get_settings()
    quota = None
    if hasattr(provider, "_quota"):
        q = provider._quota
        quota = {
            "provider": q.provider,
            "daily_limit": q.daily_limit,
            "daily_used": q.daily_used,
            "daily_remaining": q.daily_remaining,
            "reserve": q.reserve,
            "per_minute_limit": q.per_minute_limit,
            "note": "Kota doldugunda ucretli plana OTOMATIK gecis yapilmaz.",
        }

    match_count = db.scalar(select(func.count()).select_from(Match)) or 0
    league_count = db.scalar(select(func.count()).select_from(League)) or 0
    pred_count = db.scalar(select(func.count()).select_from(Prediction)) or 0
    settled = db.scalar(select(func.count()).select_from(PredictionOutcome).where(PredictionOutcome.actual.is_not(None))) or 0
    last_refresh = db.scalar(select(func.max(Match.last_updated_at)))

    return {
        "server_time": datetime.now(timezone.utc).isoformat(),
        "provider": {
            "name": provider.name,
            "configured": provider.is_configured(),
            "mode": settings.provider_mode,
            "config_hint": None
            if provider.is_configured()
            else "API_FOOTBALL_KEY ortam degiskeni tanimli degil (.env). Anahtar olmadan canli veri alinamaz.",
        },
        "quota": quota,
        "target_competitions": TARGET_COMPETITIONS,        "counts": {
            "leagues": league_count,
            "matches": match_count,
            "predictions": pred_count,
            "settled_predictions": settled,
        },
        "last_successful_refresh": last_refresh.isoformat() if last_refresh else None,
        "secondary_provider": {
            "name": "football-data.org",
            "configured": settings.football_data_configured,
            "coverage_note": (
                "Ucretsiz katmanda yalnizca La Liga, Serie A, Ligue 1 ve Sampiyonlar Ligi (TIER_ONE). "
                "Super Lig, Avrupa Ligi ve Konferans Ligi ucretsiz katmanda YOK; canli ayrintili istatistik sunmaz."
            ),
        },
    }
