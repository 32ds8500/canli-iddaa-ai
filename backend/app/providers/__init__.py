"""Saglayici fabrikasi ve desteklenen organizasyon tanimlari."""
from __future__ import annotations

from app.config import Settings, get_settings
from app.providers.api_football import ApiFootballProvider
from app.providers.base import FootballProvider
from app.providers.football_data import FootballDataProvider
from app.providers.fotmob import FOTMOB_LEAGUE_IDS, FotMobProvider

# Desteklenen 7 organizasyon. API-Football kimlikleri, gercek /leagues yanitiyla
# DOGRULANMALIDIR (scripts/verify_leagues.py). Buradaki degerler yalnizca
# dogrulama baslangic noktasidir; kesin kabul edilmez.
TARGET_COMPETITIONS: list[dict[str, str]] = [
    {"key": "super_lig", "name": "Turkiye Super Lig", "api_football_id": "203"},
    {"key": "serie_a", "name": "Italya Serie A", "api_football_id": "135"},
    {"key": "la_liga", "name": "Ispanya La Liga", "api_football_id": "140"},
    {"key": "ligue_1", "name": "Fransa Ligue 1", "api_football_id": "61"},
    {"key": "champions_league", "name": "UEFA Sampiyonlar Ligi", "api_football_id": "2"},
    {"key": "europa_league", "name": "UEFA Avrupa Ligi", "api_football_id": "3"},
    {"key": "conference_league", "name": "UEFA Konferans Ligi", "api_football_id": "848"},
]

TARGET_LEAGUE_IDS: list[str] = [c["api_football_id"] for c in TARGET_COMPETITIONS]


def get_provider(settings: Settings | None = None) -> FootballProvider:
    """Yapilandirmaya gore saglayici secer.

    - provider_mode=api-football -> yalnizca API-Football
    - provider_mode=fotmob       -> yalnizca FotMob (anahtarsiz)
    - provider_mode=auto         -> API-Football anahtari varsa o, yoksa FotMob
    """
    settings = settings or get_settings()
    mode = (settings.provider_mode or "auto").strip().lower()
    if mode == "fotmob":
        return FotMobProvider(settings)
    if mode == "api-football":
        return ApiFootballProvider(settings)
    if settings.api_football_configured:
        return ApiFootballProvider(settings)
    return FotMobProvider(settings)


def get_secondary_provider(settings: Settings | None = None) -> FootballProvider:
    return FootballDataProvider(settings or get_settings())
