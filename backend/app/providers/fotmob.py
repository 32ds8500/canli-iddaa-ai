"""FotMob saglayicisi (anahtarsiz, ikincil/yedek).

API-Football hesabi kullanilamadiginda gercek canli veri saglar.
Kimlik dogrulama gerektirmez; yalnizca herkese acik JSON uclari kullanilir.
Olmayan istatistik None kalir; veri uydurulmaz.

Uclar:
- GET /api/data/matches?date=YYYYMMDD         -> gunun maclari (skor, durum, dakika)
- GET /api/data/matchDetails?matchId=<id>     -> istatistik, olaylar, xG, korner

Lig kimlikleri FotMob'a aittir (API-Football kimliklerinden farklidir).
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

import httpx

from app.config import Settings
from app.providers.base import (
    FootballProvider,
    FixtureEvent,
    FixtureStatistics,
    LeagueDTO,
    LiveFixture,
    ProviderError,
    TeamRef,
    TeamStats,
)

# FotMob lig kimlikleri (gercek /api/data/matches yanitindan gozlemlenmistir)
FOTMOB_LEAGUE_IDS: dict[str, str] = {
    "203": "71",      # Turkiye Super Lig
    "135": "55",      # Italya Serie A
    "140": "87",      # Ispanya La Liga
    "61": "53",       # Fransa Ligue 1
    "2": "42",        # UEFA Sampiyonlar Ligi
    "3": "73",        # UEFA Avrupa Ligi
    "848": "10216",   # UEFA Konferans Ligi
}
FOTMOB_TO_TARGET = {v: k for k, v in FOTMOB_LEAGUE_IDS.items()}

STATUS_MAP = {
    "1H": "1H",
    "2H": "2H",
    "HT": "HT",
    "ET": "ET",
    "BT": "BT",
    "P": "P",
    "FT": "FT",
    "AET": "AET",
    "PEN": "PEN",
}

_STAT_KEYS = {
    "BallPossesion": "possession",
    "expected_goals": "xg",
    "total_shots": "shots_total",
    "ShotsOnTarget": "shots_on",
    "ShotsOffTarget": "shots_off",
    "blocked_shots": "shots_blocked",
    "corners": "corners",
    "yellow_cards": "yellow_cards",
    "red_cards": "red_cards",
}


def _num(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().split(" ")[0].replace("%", "")
    try:
        return float(text)
    except ValueError:
        return None


def _int(value: Any) -> int | None:
    v = _num(value)
    return int(v) if v is not None else None


class FotMobProvider(FootballProvider):
    name = "fotmob"

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        client: httpx.Client | None = None,
        base_url: str = "https://www.fotmob.com",
    ) -> None:
        self.settings = settings
        self.base_url = base_url.rstrip("/")
        self._client = client or httpx.Client(
            timeout=getattr(settings, "http_timeout_seconds", 20),
            headers={
                "User-Agent": "Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36 Chrome/120 Mobile Safari/537.36",
                "Accept": "application/json",
            },
        )
        self._owns_client = client is None
        self._cache: dict[str, tuple[float, Any]] = {}

    def is_configured(self) -> bool:
        return True

    def map_target_league_ids(self, target_ids: list[str]) -> list[str]:
        return [FOTMOB_LEAGUE_IDS[i] for i in target_ids if i in FOTMOB_LEAGUE_IDS]

    def _get(self, path: str, params: dict[str, Any] | None = None, ttl: float = 30.0) -> Any:
        key = f"{path}?{sorted((params or {}).items())}"
        now = time.time()
        cached = self._cache.get(key)
        if cached and now - cached[0] < ttl:
            return cached[1]
        url = f"{self.base_url}/{path.lstrip('/')}"
        last_exc: Exception | None = None
        for attempt in range(3):
            try:
                resp = self._client.get(url, params=params)
            except httpx.HTTPError as exc:
                last_exc = exc
                time.sleep(min(2**attempt, 6))
                continue
            if resp.status_code == 429 or resp.status_code >= 500:
                last_exc = ProviderError(f"FotMob yaniti {resp.status_code}", status_code=resp.status_code, retryable=True)
                time.sleep(min(2**attempt, 6))
                continue
            if resp.status_code != 200:
                raise ProviderError(f"FotMob beklenmeyen yanit ({resp.status_code})", status_code=resp.status_code)
            data = resp.json()
            self._cache[key] = (now, data)
            return data
        raise ProviderError(f"FotMob istegi basarisiz: {last_exc}", retryable=True)

    def get_leagues(self, provider_league_ids: list[str] | None = None) -> list[LeagueDTO]:
        ids = provider_league_ids or list(FOTMOB_TO_TARGET.keys())
        out: list[LeagueDTO] = []
        for raw in ids:
            fid = FOTMOB_LEAGUE_IDS.get(str(raw), str(raw))
            target = FOTMOB_TO_TARGET.get(fid)
            if target is None:
                continue
            out.append(
                LeagueDTO(
                    provider_league_id=str(fid),
                    name=_LEAGUE_NAMES.get(target, f"FotMob lig {fid}"),
                    country=_LEAGUE_COUNTRIES.get(target),
                    kind="cup" if target in {"2", "3", "848"} else "league",
                    current_season=datetime.now(timezone.utc).year,
                    cov_live_stats=True,
                    cov_corners=True,
                    cov_dangerous_attacks=False,
                    cov_xg=True,
                    coverage_notes="FotMob: xG, sut, korner, kart ve topa sahip olma gozlemlendi; tehlikeli atak yok.",
                )
            )
        return out

    def get_live_fixtures(self, league_ids: list[str] | None = None) -> list[LiveFixture]:
        today = datetime.now(timezone.utc).strftime("%Y%m%d")
        data = self._get("api/data/matches", {"date": today}, ttl=20)
        out: list[LiveFixture] = []
        for league in data.get("leagues", []):
            fid = str(league.get("id"))
            if fid not in FOTMOB_TO_TARGET:
                continue
            for m in league.get("matches", []):
                status = m.get("status") or {}
                if not status.get("started") or status.get("finished") or status.get("cancelled"):
                    continue
                out.append(self._to_fixture(league, m, status))
        return out

    def get_fixtures_by_date(self, date: str) -> list[LiveFixture]:
        compact = date.replace("-", "")
        data = self._get("api/data/matches", {"date": compact}, ttl=60)
        out: list[LiveFixture] = []
        for league in data.get("leagues", []):
            fid = str(league.get("id"))
            if fid not in FOTMOB_TO_TARGET:
                continue
            for m in league.get("matches", []):
                out.append(self._to_fixture(league, m, m.get("status") or {}))
        return out

    def _to_fixture(self, league: dict, m: dict, status: dict) -> LiveFixture:
        fid = str(league.get("id"))
        home = m.get("home") or {}
        away = m.get("away") or {}
        started = bool(status.get("started"))
        finished = bool(status.get("finished"))
        cancelled = bool(status.get("cancelled"))
        halfs = status.get("halfs") or {}
        if cancelled:
            short = "SUSP"
        elif finished:
            short = "FT"
        elif halfs.get("secondHalfStarted"):
            short = "2H"
        elif halfs.get("firstHalfStarted") and halfs.get("firstHalfEnded"):
            short = "HT"
        elif started:
            short = "1H"
        else:
            short = "NS"
        elapsed = _elapsed_minutes(status) if started and not finished else None
        return LiveFixture(
            provider_fixture_id=str(m.get("id")),
            league_provider_id=fid,
            league_name=league.get("name", ""),
            league_country=league.get("ccode"),
            season=None,
            home=TeamRef(str(home.get("id")), home.get("name") or home.get("shortName") or ""),
            away=TeamRef(str(away.get("id")), away.get("name") or away.get("shortName") or ""),
            kickoff_at=_parse_utc(status.get("utcTime")),
            status_short=short,
            status_long=status.get("reason", {}).get("long") if isinstance(status.get("reason"), dict) else None,
            elapsed_minute=elapsed,
            home_goals=_int(home.get("score")),
            away_goals=_int(away.get("score")),
        )

    def get_fixture_statistics(self, provider_fixture_id: str) -> FixtureStatistics:
        data = self._get("api/data/matchDetails", {"matchId": provider_fixture_id}, ttl=30)
        periods = (((data.get("content") or {}).get("stats") or {}).get("Periods") or {})
        block = periods.get("All") or {}
        groups = block.get("stats") or []
        home = TeamStats(side="home")
        away = TeamStats(side="away")
        seen: set[str] = set()
        for group in groups:
            for entry in group.get("stats", []):
                key = entry.get("key")
                field = _STAT_KEYS.get(key)
                if not field or field in seen:
                    continue
                values = entry.get("stats") or []
                if len(values) < 2:
                    continue
                setattr(home, field, _num(values[0]))
                setattr(away, field, _num(values[1]))
                seen.add(field)
        if not seen:
            return FixtureStatistics(
                provider_fixture_id=provider_fixture_id,
                stats=[],
                source=self.name,
                available=False,
                note="FotMob bu mac icin istatistik dondurmedi.",
            )
        for side in (home, away):
            for attr in ("possession", "shots_total", "shots_on", "shots_off", "shots_blocked", "corners", "yellow_cards", "red_cards"):
                val = getattr(side, attr)
                if val is not None:
                    setattr(side, attr, int(val))
        return FixtureStatistics(
            provider_fixture_id=provider_fixture_id,
            stats=[home, away],
            source=self.name,
            available=True,
        )

    def get_fixture_events(
        self,
        provider_fixture_id: str,
        *,
        home_team_id: str | None = None,
        away_team_id: str | None = None,
    ) -> list[FixtureEvent]:
        data = self._get("api/data/matchDetails", {"matchId": provider_fixture_id}, ttl=30)
        events = (((data.get("content") or {}).get("matchFacts") or {}).get("events") or {})
        raw = events.get("events") if isinstance(events, dict) else events
        out: list[FixtureEvent] = []
        for idx, ev in enumerate(raw or []):
            is_home = ev.get("isHome")
            side = "home" if is_home is True else ("away" if is_home is False else None)
            out.append(
                FixtureEvent(
                    provider_event_id=f"{provider_fixture_id}:{ev.get('eventId', idx)}",
                    minute=_int(ev.get("time")),
                    extra_minute=_int(ev.get("overloadTime")),
                    type=ev.get("type"),
                    detail=ev.get("goalDescription") or ev.get("card"),
                    side=side,
                    player=(ev.get("player") or {}).get("name") if isinstance(ev.get("player"), dict) else ev.get("nameStr"),
                    assist=None,
                    comments=ev.get("swap") if isinstance(ev.get("swap"), str) else None,
                )
            )
        return out


_LEAGUE_NAMES = {
    "203": "Turkiye Super Lig",
    "135": "Italya Serie A",
    "140": "Ispanya La Liga",
    "61": "Fransa Ligue 1",
    "2": "UEFA Sampiyonlar Ligi",
    "3": "UEFA Avrupa Ligi",
    "848": "UEFA Konferans Ligi",
}
_LEAGUE_COUNTRIES = {
    "203": "Turkey",
    "135": "Italy",
    "140": "Spain",
    "61": "France",
    "2": "Europe",
    "3": "Europe",
    "848": "Europe",
}


def _parse_utc(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _elapsed_minutes(status: dict) -> int | None:
    halfs = status.get("halfs") or {}
    now = datetime.now(timezone.utc)

    def parse(text: str | None) -> datetime | None:
        if not text:
            return None
        try:
            return datetime.strptime(text, "%d.%m.%Y %H:%M:%S").replace(tzinfo=timezone.utc)
        except ValueError:
            return None

    first = parse(halfs.get("firstHalfStarted"))
    second = parse(halfs.get("secondHalfStarted"))
    first_end = parse(halfs.get("firstHalfEnded"))
    if second:
        return min(90, 45 + int((now - second).total_seconds() // 60))
    if first:
        if first_end:
            return 45
        return min(45, int((now - first).total_seconds() // 60))
    return None
