"""TEST-ONLY saglayici.

Bu saglayici YALNIZCA birim/entegrasyon testlerinde kullanilir. Gercek
canli veri yerine gecmez ve uretim akisinda kullanilmaz. Test senaryolari
acikca tanimlanmis, sonucu bilinen verilerdir.
"""
from __future__ import annotations

from app.providers.base import (
    FootballProvider,
    FixtureEvent,
    FixtureStatistics,
    LeagueDTO,
    LiveFixture,
)


class FixtureProvider(FootballProvider):
    name = "fixture-test"

    def __init__(
        self,
        *,
        leagues: list[LeagueDTO] | None = None,
        live: list[LiveFixture] | None = None,
        stats: dict[str, FixtureStatistics] | None = None,
        events: dict[str, list[FixtureEvent]] | None = None,
        configured: bool = True,
    ) -> None:
        self._leagues = leagues or []
        self._live = live or []
        self._stats = stats or {}
        self._events = events or {}
        self._configured = configured

    def is_configured(self) -> bool:
        return self._configured

    def get_leagues(self, provider_league_ids: list[str] | None = None) -> list[LeagueDTO]:
        return self._leagues

    def get_live_fixtures(self) -> list[LiveFixture]:
        return self._live

    def get_fixture_statistics(self, provider_fixture_id: str) -> FixtureStatistics:
        return self._stats.get(
            provider_fixture_id,
            FixtureStatistics(
                provider_fixture_id=provider_fixture_id, stats=[], source=self.name, available=False
            ),
        )

    def get_fixture_events(self, provider_fixture_id: str, **_: str | None) -> list[FixtureEvent]:
        return self._events.get(provider_fixture_id, [])
