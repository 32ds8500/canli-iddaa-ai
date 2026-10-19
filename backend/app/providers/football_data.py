"""football-data.org ikincil saglayicisi.

ONEMLI KAPSAM NOTU (gercek API planlariyla dogrulanmistir):
- Ucretsiz katmanda (TIER_ONE) yalnizca sinirli organizasyon vardir:
  La Liga (PD), Serie A (SA), Ligue 1 (FL1), Sampiyonlar Ligi (CL).
- Turkiye Super Lig (2070=TIER_THREE), UEFA Avrupa Ligi (2146=TIER_TWO),
  UEFA Konferans Ligi (2154=TIER_FOUR) ucretsiz katmanda YOKTUR.
- Canli (in-play) ayrintili istatistikler (sut/korner) ucretsiz katmanda sunulmaz.
Bu nedenle bu saglayici yalnizca fikstur/skor yedegi olarak kullanilir;
canli istatistik gerektiren yerde kullanilmaz.
"""
from __future__ import annotations

import httpx

from app.config import Settings
from app.providers.base import (
    FootballProvider,
    FixtureEvent,
    FixtureStatistics,
    LeagueDTO,
    LiveFixture,
    NotConfiguredError,
    ProviderError,
    TeamRef,
)
from app.providers.cache import TTLCache
from app.providers.quota import QuotaExceededError, QuotaManager

LIVE_STATUSES = {"IN_PLAY", "PAUSED"}


class FootballDataProvider(FootballProvider):
    name = "football-data"

    def __init__(self, settings: Settings, *, client: httpx.Client | None = None) -> None:
        self.settings = settings
        self.base_url = settings.football_data_base_url.rstrip("/")
        self._key = settings.football_data_key.strip()
        self._client = client or httpx.Client(timeout=settings.http_timeout_seconds)
        self._cache = TTLCache()
        self._quota = QuotaManager("football-data", 10, 10, 0)

    def is_configured(self) -> bool:
        return bool(self._key)

    def _request(self, path: str, params: dict | None = None, ttl: float = 60) -> dict:
        if not self._key:
            raise NotConfiguredError("football-data.org", "FOOTBALL_DATA_KEY")
        cache_key = f"{path}?{sorted((params or {}).items())}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached
        url = f"{self.base_url}/{path.lstrip('/')}"
        try:
            self._quota.acquire()
        except QuotaExceededError as exc:
            raise ProviderError(str(exc), status_code=429) from exc
        try:
            resp = self._client.get(url, headers={"X-Auth-Token": self._key}, params=params)
        except httpx.HTTPError as exc:
            self._quota.release()
            raise ProviderError(f"Ag hatasi: {exc}", retryable=True) from exc
        if resp.status_code in (401, 403):
            raise ProviderError(
                "football-data.org yetki hatasi veya plan kisiti (TIER yetersiz)",
                status_code=resp.status_code,
            )
        if resp.status_code != 200:
            raise ProviderError(f"Beklenmeyen yanit ({resp.status_code})", status_code=resp.status_code)
        data = resp.json()
        self._cache.set(cache_key, data, ttl)
        return data

    def get_leagues(self, provider_league_ids: list[str] | None = None) -> list[LeagueDTO]:
        data = self._request("competitions", ttl=86400)
        out: list[LeagueDTO] = []
        wanted = {str(x) for x in provider_league_ids} if provider_league_ids else None
        for c in data.get("competitions", []):
            cid = str(c.get("id"))
            if wanted and cid not in wanted:
                continue
            out.append(
                LeagueDTO(
                    provider_league_id=cid,
                    name=c.get("name", ""),
                    country=c.get("area", {}).get("name"),
                    kind="cup",
                    current_season=(c.get("currentSeason") or {}).get("startDate", "")[:4] or None,
                    cov_live_stats=False,
                    cov_corners=False,
                    cov_dangerous_attacks=False,
                    cov_xg=False,
                    coverage_notes="Canli ayrintili istatistik bu planda sunulmaz.",
                )
            )
        return out

    def get_live_fixtures(self) -> list[LiveFixture]:
        data = self._request("matches", {"status": "IN_PLAY,PAUSED"}, ttl=45)
        out: list[LiveFixture] = []
        for m in data.get("matches", []):
            score = m.get("score", {}).get("fullTime", {})
            out.append(
                LiveFixture(
                    provider_fixture_id=str(m.get("id")),
                    league_provider_id=str((m.get("competition") or {}).get("id")),
                    league_name=(m.get("competition") or {}).get("name", ""),
                    league_country=(m.get("area") or {}).get("name"),
                    season=(m.get("season") or {}).get("startDate", "")[:4] or None,
                    home=TeamRef(str((m.get("homeTeam") or {}).get("id")), (m.get("homeTeam") or {}).get("name", "")),
                    away=TeamRef(str((m.get("awayTeam") or {}).get("id")), (m.get("awayTeam") or {}).get("name", "")),
                    kickoff_at=m.get("utcDate"),
                    status_short=m.get("status", ""),
                    status_long=m.get("status"),
                    elapsed_minute=m.get("minute"),
                    home_goals=score.get("home"),
                    away_goals=score.get("away"),
                )
            )
        return out

    def get_fixture_statistics(self, provider_fixture_id: str) -> FixtureStatistics:
        return FixtureStatistics(
            provider_fixture_id=provider_fixture_id,
            stats=[],
            source=self.name,
            available=False,
            note="football-data.org canli ayrintili istatistik sunmuyor.",
        )

    def get_fixture_events(self, provider_fixture_id: str, **_: str | None) -> list[FixtureEvent]:
        return []
