"""FastAPI bagimliliklari ve paylasilan nesneler."""
from __future__ import annotations

from functools import lru_cache

from app.config import get_settings
from app.db import SessionLocal
from app.ingest.live import LiveIngestService
from app.models import ApiUsageLog
from app.providers import TARGET_LEAGUE_IDS
from app.providers.api_football import ApiFootballProvider
from app.providers.base import FootballProvider


def _usage_logger(endpoint: str, status_code: int | None, cached: bool) -> None:
    try:
        db = SessionLocal()
        db.add(ApiUsageLog(provider="api-football", endpoint=endpoint, status_code=status_code, cached=cached))
        db.commit()
        db.close()
    except Exception:  # noqa: BLE001 - log yazimi uygulamayi durdurmamali
        pass


@lru_cache
def get_provider_singleton() -> FootballProvider:
    return ApiFootballProvider(get_settings(), usage_logger=_usage_logger)


@lru_cache
def get_ingest_singleton() -> LiveIngestService:
    return LiveIngestService(get_provider_singleton(), TARGET_LEAGUE_IDS)


def get_provider_dep() -> FootballProvider:
    return get_provider_singleton()


def get_ingest_dep() -> LiveIngestService:
    return get_ingest_singleton()
