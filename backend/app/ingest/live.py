"""Canli veri cekme servisi.

Kota stratejisi (ucretsiz plan = 100 istek/gun):
- Canli liste: saglayicinin `fixtures?live=<ligler>` cagrisi TEK istekle
  ilgili liglerdeki tum canli maclari getirir (kota dostu).
- Ayrintili istatistik (sut/korner) mac BASINA ayri cagri gerektirir;
  bu yuzden yalnizca izlenen (watchlist) maclar icin ve seyrek cekilir.
- Zamanlayici, gunluk butceye gore araligi otomatik ayarlar; butce asilirsa
  cagri yapmaz (ucretli plana gecmez).
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ingest.normalizer import Normalizer, match_pk
from app.models import Match, MatchStat
from app.providers.base import FootballProvider, ProviderError

LIVE_SHORT_STATUSES = {"1H", "2H", "HT", "ET", "BT", "P", "LIVE", "IN_PLAY", "PAUSED", "SUSP", "INT"}
NOT_STARTED = {"NS", "TBD"}


class LiveIngestService:
    def __init__(self, provider: FootballProvider, target_league_ids: list[str]) -> None:
        self.provider = provider
        self.target_league_ids = target_league_ids
        self.normalizer = Normalizer(provider.name)

    def refresh_live(self, db: Session) -> list[Match]:
        """Ilgili liglerdeki canli maclari ceker ve kaydeder."""
        fixtures = self.provider.get_live_fixtures()  # type: ignore[call-arg]
        if not fixtures:
            fixtures = []
        target = set(self.target_league_ids)
        matches: list[Match] = []
        for fx in fixtures:
            if target and fx.league_provider_id not in target:
                continue
            match = self.normalizer.upsert_live_fixture(db, fx)
            matches.append(match)
        db.commit()
        for m in matches:
            db.refresh(m)
        return matches

    def refresh_day(self, db: Session, date: str) -> list[Match]:
        """Yerel (UTC+3) gunun maclarini kaydeder.

        Saglayici tarihleri UTC gunune gore listeler; yerel gun 21:00 UTC'de
        basladigi icin bir onceki UTC gunu de cekilir, aksi halde 00:00-03:00
        arasindaki maclar kacar.
        """
        from datetime import date as _date, timedelta

        try:
            local_day = _date.fromisoformat(date)
        except ValueError:
            local_day = None
        provider_dates = [date]
        if local_day is not None:
            provider_dates.append((local_day - timedelta(days=1)).isoformat())

        target = set(self.target_league_ids)
        seen: set[str] = set()
        matches: list[Match] = []
        for provider_date in provider_dates:
            try:
                fixtures = self.provider.get_fixtures_by_date(provider_date)
            except ProviderError:
                fixtures = []
            for fx in fixtures:
                if target and fx.league_provider_id not in target:
                    continue
                if fx.provider_fixture_id in seen:
                    continue
                seen.add(fx.provider_fixture_id)
                matches.append(self.normalizer.upsert_live_fixture(db, fx))
        db.commit()
        for m in matches:
            db.refresh(m)
        return matches

    def enrich_match(self, db: Session, match: Match) -> None:
        """Bir macin istatistik ve olaylarini ceker (mac basina 2 istek)."""
        stats = self.provider.get_fixture_statistics(match.provider_fixture_id)
        self.normalizer.apply_statistics(db, match, stats)
        self._update_league_coverage(db, match, stats)
        try:
            from app.models import Team  # yerel import (dairesel bagimlilik yok)

            home = db.get(Team, match.home_team_id)
            away = db.get(Team, match.away_team_id)
            events = self.provider.get_fixture_events(
                match.provider_fixture_id,
                home_team_id=home.provider_team_id if home else None,
                away_team_id=away.provider_team_id if away else None,
            )
        except ProviderError:
            events = []
        self.normalizer.apply_events(db, match, events)
        db.flush()

        stats_by_side = {
            row.side: row
            for row in db.execute(select(MatchStat).where(MatchStat.match_id == match.id)).scalars()
        }
        match.data_quality = self.normalizer.assess_quality(match, stats_by_side)
        match.last_updated_at = datetime.now(timezone.utc)
        db.commit()

    def _update_league_coverage(self, db: Session, match: Match, stats) -> None:
        """Gozlemlenen istatistiklere gore lig kapsam bayraklarini gunceller."""
        from app.models import League

        league = db.get(League, match.league_id)
        if league is None or not stats.available:
            return
        fields = {f for ts in stats.stats for f in (
            "shots_total", "shots_on", "corners", "dangerous_attacks", "xg"
        ) if getattr(ts, f) is not None}
        if fields:
            league.cov_live_stats = True
        if "corners" in fields:
            league.cov_corners = True
        if "dangerous_attacks" in fields:
            league.cov_dangerous_attacks = True
        if "xg" in fields:
            league.cov_xg = True
        if "dangerous_attacks" not in fields and league.cov_dangerous_attacks is False:
            league.coverage_notes = "Tehlikeli atak verisi saglayicida gozlemlenmedi."

    @staticmethod
    def compute_data_age_seconds(match: Match) -> int | None:
        if match.last_updated_at is None:
            return None
        ref = match.last_updated_at
        if ref.tzinfo is None:
            ref = ref.replace(tzinfo=timezone.utc)
        return int((datetime.now(timezone.utc) - ref).total_seconds())
