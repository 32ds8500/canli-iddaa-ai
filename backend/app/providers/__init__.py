"""Saglayici fabrikasi ve desteklenen organizasyon tanimlari."""
from __future__ import annotations

from app.config import Settings, get_settings
from app.providers.api_football import ApiFootballProvider
from app.providers.base import FootballProvider
from app.providers.football_data import FootballDataProvider

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
    return ApiFootballProvider(settings or get_settings())


def get_secondary_provider(settings: Settings | None = None) -> FootballProvider:
    return FootballDataProvider(settings or get_settings())
