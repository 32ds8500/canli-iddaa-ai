"""API-Football (api-sports.io) saglayicisi.

Ucretsiz plan: 100 istek/gun, 10 istek/dakika, tum endpoint'ler acik.
Anahtar yoksa NotConfiguredError yukseltilir; sahte veri uretilmez.
"""
from __future__ import annotations

import time
from typing import Any, Callable

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
    TeamStats,
)
from app.providers.cache import TTLCache
from app.providers.quota import QuotaExceededError, QuotaManager

UsageLogger = Callable[[str, int | None, bool], None]


def _to_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _to_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


# API-Football istatistik "type" -> ic alan eslemesi
_STAT_MAP = {
    "total shots": "shots_total",
    "shots on goal": "shots_on",
    "shots off goal": "shots_off",
    "blocked shots": "shots_blocked",
    "corner kicks": "corners",
    "ball possession": "possession",
    "yellow cards": "yellow_cards",
    "red cards": "red_cards",
    "expected_goals": "xg",
    "dangerous attacks": "dangerous_attacks",
}


class ApiFootballProvider(FootballProvider):
    name = "api-football"

    def __init__(
        self,
        settings: Settings,
        *,
        client: httpx.Client | None = None,
        quota: QuotaManager | None = None,
        cache: TTLCache | None = None,
        usage_logger: UsageLogger | None = None,
    ) -> None:
        self.settings = settings
        self._key = settings.api_football_key.strip()
        self._rapidapi_key = settings.rapidapi_key.strip()
        self._rapidapi_host = settings.rapidapi_host.strip()
        if self._rapidapi_key and not self._key:
            self.base_url = f"https://{self._rapidapi_host}/v3"
        else:
            self.base_url = settings.api_football_base_url.rstrip("/")
        self._client = client or httpx.Client(timeout=settings.http_timeout_seconds)
        self._owns_client = client is None
        self._cache = cache or TTLCache()
        self._quota = quota or QuotaManager(
            "api-football",
            settings.daily_quota,
            settings.per_minute_quota,
            settings.quota_reserve,
        )
        self._usage_logger = usage_logger

    # --- altyapi ---
    def is_configured(self) -> bool:
        return bool(self._key or self._rapidapi_key)

    def _require_key(self) -> None:
        if not self._key and not self._rapidapi_key:
            raise NotConfiguredError("API-Football", "API_FOOTBALL_KEY veya RAPIDAPI_KEY")

    def _headers(self) -> dict[str, str]:
        if self._rapidapi_key:
            return {
                "x-rapidapi-key": self._rapidapi_key,
                "x-rapidapi-host": self._rapidapi_host,
            }
        return {"x-apisports-key": self._key}

    def _request(self, path: str, params: dict[str, Any] | None = None, *, ttl: float | None = None) -> dict:
        self._require_key()
        params = params or {}
        cache_key = f"{path}?{sorted(params.items())}"
        if ttl and ttl > 0:
            cached = self._cache.get(cache_key)
            if cached is not None:
                if self._usage_logger:
                    self._usage_logger(path, 200, True)
                return cached

        url = f"{self.base_url}/{path.lstrip('/')}"
        last_exc: Exception | None = None
        for attempt in range(self.settings.http_max_retries):
            try:
                self._quota.acquire()
            except QuotaExceededError as exc:
                raise ProviderError(str(exc), status_code=429, retryable=False) from exc
            try:
                resp = self._client.get(url, headers=self._headers(), params=params)
            except httpx.HTTPError as exc:
                self._quota.release()
                last_exc = exc
                self._sleep_backoff(attempt)
                continue

            if self._usage_logger:
                self._usage_logger(path, resp.status_code, False)

            if resp.status_code == 429:
                self._quota.release()
                last_exc = ProviderError("Hiz limiti asildi (429)", status_code=429, retryable=True)
                self._sleep_backoff(attempt)
                continue
            if resp.status_code in (401, 403):
                self._quota.release()
                raise ProviderError(
                    "API-Football kimlik dogrulama hatasi (anahtar gecersiz veya yetki yok)",
                    status_code=resp.status_code,
                )
            if resp.status_code >= 500:
                self._quota.release()
                last_exc = ProviderError(
                    f"Sunucu hatasi ({resp.status_code})", status_code=resp.status_code, retryable=True
                )
                self._sleep_backoff(attempt)
                continue
            if resp.status_code != 200:
                self._quota.release()
                raise ProviderError(f"Beklenmeyen yanit ({resp.status_code})", status_code=resp.status_code)

            data = resp.json()
            errors = data.get("errors")
            if errors and (isinstance(errors, dict) and len(errors) > 0 or isinstance(errors, list) and len(errors) > 0):
                raise ProviderError(f"API-Football hata dondurdu: {errors}", status_code=200)
            if ttl and ttl > 0:
                self._cache.set(cache_key, data, ttl)
            return data

        raise ProviderError(f"Istek basarisiz: {last_exc}", retryable=True)

    @staticmethod
    def _sleep_backoff(attempt: int) -> None:
        time.sleep(min(2 ** attempt, 8))

    # --- endpoint'ler ---
    def get_leagues(self, provider_league_ids: list[str] | None = None) -> list[LeagueDTO]:
        out: list[LeagueDTO] = []
        for lid in provider_league_ids or [None]:
            data = self._request("leagues", {"id": lid} if lid else {}, ttl=86400)
            for item in data.get("response", []):
                league = item.get("league", {})
                country = item.get("country", {})
                seasons = item.get("seasons", []) or []
                current = next((s.get("year") for s in seasons if s.get("current")), None)
                if current is None and seasons:
                    current = seasons[-1].get("year")
                out.append(
                    LeagueDTO(
                        provider_league_id=str(league.get("id")),
                        name=league.get("name", ""),
                        country=country.get("name"),
                        kind="cup" if league.get("type") == "Cup" else "league",
                        current_season=current,
                    )
                )
        return out

    def get_live_fixtures(self, league_ids: list[str] | None = None) -> list[LiveFixture]:
        params: dict[str, Any] = {}
        if league_ids:
            params["live"] = "-".join(league_ids)
        else:
            params["live"] = "all"
        data = self._request("fixtures", params, ttl=self.settings.live_cache_ttl_seconds)
        out: list[LiveFixture] = []
        for item in data.get("response", []):
            fixture = item.get("fixture", {})
            league = item.get("league", {})
            teams = item.get("teams", {})
            goals = item.get("goals", {})
            status = fixture.get("status", {})
            kickoff = fixture.get("date")
            out.append(
                LiveFixture(
                    provider_fixture_id=str(fixture.get("id")),
                    league_provider_id=str(league.get("id")),
                    league_name=league.get("name", ""),
                    league_country=league.get("country"),
                    season=league.get("season"),
                    home=TeamRef(str(teams.get("home", {}).get("id")), teams.get("home", {}).get("name", "")),
                    away=TeamRef(str(teams.get("away", {}).get("id")), teams.get("away", {}).get("name", "")),
                    kickoff_at=_parse_dt(kickoff),
                    status_short=status.get("short", "NS"),
                    status_long=status.get("long"),
                    elapsed_minute=status.get("elapsed"),
                    home_goals=goals.get("home"),
                    away_goals=goals.get("away"),
                )
            )
        return out

    def get_fixtures_by_date(self, date: str) -> list[LiveFixture]:
        data = self._request("fixtures", {"date": date}, ttl=60)
        out: list[LiveFixture] = []
        for item in data.get("response", []):
            fixture = item.get("fixture", {})
            league = item.get("league", {})
            teams = item.get("teams", {})
            goals = item.get("goals", {})
            status = fixture.get("status", {})
            out.append(
                LiveFixture(
                    provider_fixture_id=str(fixture.get("id")),
                    league_provider_id=str(league.get("id")),
                    league_name=league.get("name", ""),
                    league_country=league.get("country"),
                    season=league.get("season"),
                    home=TeamRef(str(teams.get("home", {}).get("id")), teams.get("home", {}).get("name", "")),
                    away=TeamRef(str(teams.get("away", {}).get("id")), teams.get("away", {}).get("name", "")),
                    kickoff_at=_parse_dt(fixture.get("date")),
                    status_short=status.get("short", "NS"),
                    status_long=status.get("long"),
                    elapsed_minute=status.get("elapsed"),
                    home_goals=goals.get("home"),
                    away_goals=goals.get("away"),
                )
            )
        return out

    def get_fixture_statistics(self, provider_fixture_id: str) -> FixtureStatistics:
        data = self._request(
            "fixtures/statistics", {"fixture": provider_fixture_id}, ttl=self.settings.stats_cache_ttl_seconds
        )
        response = data.get("response", [])
        if not response:
            return FixtureStatistics(
                provider_fixture_id=provider_fixture_id,
                stats=[],
                source=self.name,
                available=False,
                note="Istatistik verisi saglayici tarafindan dondurulmedi.",
            )
        stats: list[TeamStats] = []
        for idx, block in enumerate(response):
            side = "home" if idx == 0 else "away"
            parsed = TeamStats(side=side)
            for entry in block.get("statistics", []):
                field = _STAT_MAP.get((entry.get("type") or "").strip().lower())
                if not field:
                    continue
                raw = entry.get("value")
                if field == "xg":
                    setattr(parsed, field, _to_float(raw))
                elif field == "possession":
                    if isinstance(raw, str) and raw.endswith("%"):
                        raw = raw[:-1]
                    setattr(parsed, field, _to_int(raw))
                else:
                    setattr(parsed, field, _to_int(raw))
            stats.append(parsed)
        return FixtureStatistics(
            provider_fixture_id=provider_fixture_id, stats=stats, source=self.name, available=True
        )

    def get_fixture_events(
        self,
        provider_fixture_id: str,
        *,
        home_team_id: str | None = None,
        away_team_id: str | None = None,
    ) -> list[FixtureEvent]:
        data = self._request(
            "fixtures/events", {"fixture": provider_fixture_id}, ttl=self.settings.stats_cache_ttl_seconds
        )
        out: list[FixtureEvent] = []
        for idx, item in enumerate(data.get("response", [])):
            time_info = item.get("time", {})
            team_id = str((item.get("team") or {}).get("id")) if (item.get("team") or {}).get("id") else None
            side: str | None = None
            if team_id is not None and home_team_id is not None and team_id == str(home_team_id):
                side = "home"
            elif team_id is not None and away_team_id is not None and team_id == str(away_team_id):
                side = "away"
            out.append(
                FixtureEvent(
                    provider_event_id=f"{provider_fixture_id}:{idx}",
                    minute=time_info.get("elapsed"),
                    extra_minute=time_info.get("extra"),
                    type=item.get("type"),
                    detail=item.get("detail"),
                    side=side,
                    player=(item.get("player") or {}).get("name"),
                    assist=(item.get("assist") or {}).get("name"),
                    comments=item.get("comments"),
                )
            )
        return out

    def get_status(self) -> dict:
        return self._request("status", {}, ttl=0)


def _parse_dt(value: Any):
    from datetime import datetime

    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
