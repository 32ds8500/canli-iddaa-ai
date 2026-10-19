"""Saglayici bagimsiz veri transfer nesneleri ve saglayici arayuzu.

Bu katman, saglayicidan gelen ham veriyi normalize eder. Saglayicida
bulunmayan bir istatistik daima None olarak tasinir; uydurulmaz.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class TeamRef:
    provider_team_id: str
    name: str


@dataclass
class LeagueDTO:
    provider_league_id: str
    name: str
    country: str | None
    kind: str  # league|cup
    current_season: int | None
    cov_live_stats: bool = False
    cov_corners: bool = False
    cov_dangerous_attacks: bool = False
    cov_xg: bool = False
    coverage_notes: str | None = None


@dataclass
class LiveFixture:
    provider_fixture_id: str
    league_provider_id: str
    league_name: str
    league_country: str | None
    season: int | None
    home: TeamRef
    away: TeamRef
    kickoff_at: datetime | None
    status_short: str
    status_long: str | None
    elapsed_minute: int | None
    home_goals: int | None
    away_goals: int | None


@dataclass
class TeamStats:
    side: str  # home|away
    shots_total: int | None = None
    shots_on: int | None = None
    shots_off: int | None = None
    shots_blocked: int | None = None
    corners: int | None = None
    dangerous_attacks: int | None = None
    possession: int | None = None
    yellow_cards: int | None = None
    red_cards: int | None = None
    xg: float | None = None


@dataclass
class FixtureStatistics:
    provider_fixture_id: str
    stats: list[TeamStats] = field(default_factory=list)
    source: str | None = None
    available: bool = True
    note: str | None = None


@dataclass
class FixtureEvent:
    provider_event_id: str
    minute: int | None
    extra_minute: int | None
    type: str | None
    detail: str | None
    side: str | None
    player: str | None
    assist: str | None
    comments: str | None


class ProviderError(RuntimeError):
    """Saglayici kaynakli hata (ag, kimlik, kota)."""

    def __init__(self, message: str, *, status_code: int | None = None, retryable: bool = False):
        super().__init__(message)
        self.status_code = status_code
        self.retryable = retryable


class NotConfiguredError(ProviderError):
    """Saglayici anahtari tanimli degil."""

    def __init__(self, provider: str, env_var: str):
        super().__init__(
            f"{provider} saglayicisi yapilandirilmamis. Lutfen {env_var} ortam degiskenini ayarlayin."
        )
        self.provider = provider
        self.env_var = env_var


class FootballProvider(ABC):
    """Tum saglayicilarin uygulamasi gereken arayuz."""

    name: str = "base"

    @abstractmethod
    def is_configured(self) -> bool: ...

    @abstractmethod
    def get_leagues(self, provider_league_ids: list[str] | None = None) -> list[LeagueDTO]:
        """Organizasyon meta verisi + veri kapsamini dondurur."""

    @abstractmethod
    def get_live_fixtures(self) -> list[LiveFixture]:
        """Su anda canli olan tum maclari dondurur."""

    @abstractmethod
    def get_fixture_statistics(self, provider_fixture_id: str) -> FixtureStatistics:
        """Bir macin canli/bitmis istatistiklerini dondurur."""

    @abstractmethod
    def get_fixture_events(
        self,
        provider_fixture_id: str,
        *,
        home_team_id: str | None = None,
        away_team_id: str | None = None,
    ) -> list[FixtureEvent]:
        """Gol/kart/degisiklik olaylarini dondurur."""
