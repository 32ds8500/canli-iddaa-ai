"""Oran toplama (opsiyonel).

Gercek oranlar yalnizca yapilandirilmis bir kaynaktan alinir; oran yoksa
hicbir deger uydurulmaz. Desteklenen kaynak: The Odds API (ucretsiz plan).
"""
from __future__ import annotations

import logging
import re
import unicodedata
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.models import League, Match, Odds

logger = logging.getLogger("canli-iddaa.odds")

SPORT_KEYS: dict[str, str] = {
    "super lig": "soccer_turkey_super_lig",
    "serie a": "soccer_italy_serie_a",
    "laliga": "soccer_spain_la_liga",
    "la liga": "soccer_spain_la_liga",
    "ligue 1": "soccer_france_ligue_one",
    "champions league": "soccer_uefa_champs_league",
    "europa league": "soccer_uefa_europa_league",
    "conference league": "soccer_uefa_europa_conference_league",
}


def normalize_name(value: str) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower().replace("ı", "i").replace("ş", "s").replace("ğ", "g")
    return re.sub(r"[^a-z0-9]+", "", text)


def sport_key_for_league(name: str | None) -> str | None:
    if not name:
        return None
    low = name.lower()
    for needle, key in SPORT_KEYS.items():
        if needle in low:
            return key
    return None


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


class OddsService:
    def __init__(self, settings: Settings | None = None, *, client: httpx.Client | None = None) -> None:
        self.settings = settings or get_settings()
        self._client = client

    def is_configured(self) -> bool:
        return self.settings.odds_configured

    def _fetch(self, sport_key: str) -> list[dict]:
        params = {
            "apiKey": self.settings.odds_api_key,
            "regions": self.settings.odds_regions,
            "markets": "h2h,totals",
            "oddsFormat": "decimal",
            "dateFormat": "iso",
        }
        url = f"{self.settings.odds_api_base_url.rstrip('/')}/sports/{sport_key}/odds"
        client = self._client or httpx.Client(timeout=self.settings.http_timeout_seconds)
        try:
            res = client.get(url, params=params)
            if res.status_code != 200:
                logger.warning("Oran kaynagi %s icin %s dondurdu", sport_key, res.status_code)
                return []
            data = res.json()
            return data if isinstance(data, list) else []
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("Oran cekilemedi (%s): %s", sport_key, exc)
            return []
        finally:
            if self._client is None:
                client.close()

    def refresh(self, db: Session) -> int:
        """Bugun/yarin oynanacak hedef maclar icin oranlari gunceller."""
        if not self.is_configured():
            return 0
        now = datetime.now(timezone.utc)
        window_end = now + timedelta(days=2)

        matches = db.execute(select(Match)).scalars().all()
        pending = [
            m
            for m in matches
            if m.kickoff_at is not None and now - timedelta(hours=3) <= m.kickoff_at <= window_end
        ]
        if not pending:
            return 0

        by_league: dict[str, list[Match]] = {}
        for match in pending:
            league = db.get(League, match.league_id)
            key = sport_key_for_league(league.name if league else None)
            if key:
                by_league.setdefault(key, []).append(match)

        stored = 0
        for sport_key, league_matches in by_league.items():
            for event in self._fetch(sport_key):
                home = normalize_name(event.get("home_team", ""))
                away = normalize_name(event.get("away_team", ""))
                commence = _parse_dt(event.get("commence_time"))
                target = next(
                    (
                        m
                        for m in league_matches
                        if normalize_name(m.home_team_id) == home
                        or normalize_name(m.away_team_id) == away
                    ),
                    None,
                )
                if target is None or commence is None or target.kickoff_at is None:
                    continue
                if abs((commence - target.kickoff_at).total_seconds()) > 12 * 3600:
                    continue
                stored += self._store_event(db, target, event)
        db.commit()
        return stored

    def _store_event(self, db: Session, match: Match, event: dict) -> int:
        count = 0
        for bookmaker in event.get("bookmakers", []):
            title = bookmaker.get("title") or bookmaker.get("key")
            for market in bookmaker.get("markets", []):
                market_key = market.get("key")
                for outcome in market.get("outcomes", []):
                    price = outcome.get("price")
                    if not isinstance(price, (int, float)) or price <= 1.0:
                        continue
                    name = normalize_name(str(outcome.get("name", "")))
                    if market_key == "h2h":
                        if name in ("draw", "beraberlik", "x"):
                            selection = "draw"
                        elif name == normalize_name(match.home_team_id):
                            selection = "home"
                        else:
                            selection = "away"
                        market_name = "h2h"
                    elif market_key == "totals":
                        point = outcome.get("point")
                        if point is None:
                            continue
                        side = "over" if name in ("over", "ust") else "under"
                        market_name = f"totals_{point}_{side}"
                        selection = side
                    else:
                        continue
                    existing = (
                        db.query(Odds)
                        .filter(
                            Odds.match_id == match.id,
                            Odds.bookmaker == title,
                            Odds.market == market_name,
                            Odds.selection == selection,
                        )
                        .first()
                    )
                    if existing:
                        existing.price = float(price)
                        existing.fetched_at = datetime.now(timezone.utc)
                    else:
                        db.add(
                            Odds(
                                match_id=match.id,
                                bookmaker=title,
                                market=market_name,
                                selection=selection,
                                price=float(price),
                            )
                        )
                    count += 1
        return count


def odds_for_match(db: Session, match_id: str) -> list[dict]:
    rows = db.execute(select(Odds).where(Odds.match_id == match_id)).scalars().all()
    return [
        {
            "bookmaker": row.bookmaker,
            "market": row.market,
            "selection": row.selection,
            "price": row.price,
            "implied_probability": round(1.0 / row.price, 4) if row.price > 0 else None,
            "fetched_at": row.fetched_at.isoformat() if row.fetched_at else None,
        }
        for row in rows
    ]
