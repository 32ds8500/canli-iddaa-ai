"""Uygulama yapilandirmasi.

API anahtarlari yalnizca sunucu tarafinda tutulur; frontend'e asla gonderilmez.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Saglayicilar ---
    api_football_key: str = ""
    api_football_base_url: str = "https://v3.football.api-sports.io"

    rapidapi_key: str = ""
    rapidapi_host: str = "api-football-v1.p.rapidapi.com"

    # auto|api-football|fotmob
    provider_mode: str = "auto"

    # all: gunun tum ligleri; selected: yalnizca TARGET_LEAGUE_IDS
    league_scope: str = "all"

    # --- Oranlar (opsiyonel; The Odds API ucretsiz plan) ---
    odds_api_key: str = ""
    odds_api_base_url: str = "https://api.the-odds-api.com/v4"
    odds_regions: str = "eu"
    odds_refresh_interval_seconds: int = 1800

    football_data_key: str = ""
    football_data_base_url: str = "https://api.football-data.org/v4"

    # --- Veritabani ---
    database_url: str = "sqlite:///./data/app.db"

    # --- Kota yonetimi ---
    daily_quota: int = 100
    per_minute_quota: int = 10
    quota_reserve: int = 15

    # --- Onbellek / HTTP ---
    live_cache_ttl_seconds: int = 60
    stats_cache_ttl_seconds: int = 45
    http_timeout_seconds: int = 20
    http_max_retries: int = 3

    # --- Zamanlanmis gorevler ---
    live_poll_interval_seconds: int = 180
    # Bir turda istatistigi cekilecek canli mac sayisi (FotMob ucretsiz; API-Football kotaya takilir)
    live_enrich_limit: int = 200
    # Bu kadari icin tahminler olcüm amaciyla veritabanina da yazilir
    live_persist_limit: int = 6
    outcome_settle_interval_seconds: int = 300
    enable_scheduler: bool = True

    # --- Arayuz / saat dilimi ---
    # Gun sinirlari ve gunluk kota bu ofsete gore hesaplanir.
    # Turkiye 2016'dan beri kalici UTC+3 (yaz saati yok).
    app_utc_offset_hours: int = 3
    cors_origins: str = "*"

    @property
    def api_football_configured(self) -> bool:
        return bool(self.api_football_key.strip() or self.rapidapi_key.strip())

    @property
    def odds_configured(self) -> bool:
        return bool(self.odds_api_key.strip())

    @property
    def football_data_configured(self) -> bool:
        return bool(self.football_data_key.strip())

    def ensure_data_dir(self) -> None:
        if self.database_url.startswith("sqlite"):
            raw = self.database_url.split("sqlite:///")[-1]
            path = Path(raw)
            if not path.is_absolute():
                path = BACKEND_DIR / path
            path.parent.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()
