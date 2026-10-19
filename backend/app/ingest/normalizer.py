"""Ham saglayici verisini veritabanina normalize eden katman.

Ilkeler:
- Olmayan istatistik None olarak kalir; uydurulmaz.
- Eksik/celiskili/gecikmis veri isaretlenir (data_quality).
- Olaylar ve istatistikler idempotent sekilde (upsert) yazilir.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import League, Match, MatchEvent, MatchStat, Team
from app.providers.base import FixtureEvent, FixtureStatistics, LeagueDTO, LiveFixture

# Durum kodlari -> insan okunur durum
LIVE_STATUSES = {"1H", "2H", "HT", "ET", "BT", "P", "LIVE", "IN_PLAY", "PAUSED"}
FINISHED_STATUSES = {"FT", "AET", "PEN", "FINISHED"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def league_pk(provider: str, provider_id: str) -> str:
    return f"{provider}:{provider_id}"


def team_pk(provider: str, provider_id: str) -> str:
    return f"{provider}:{provider_id}"


def match_pk(provider: str, provider_id: str) -> str:
    return f"{provider}:{provider_id}"


class Normalizer:
    def __init__(self, provider_name: str) -> None:
        self.provider = provider_name

    # --- ligler / takimlar ---
    def upsert_league(self, db: Session, dto: LeagueDTO) -> League:
        db.flush()
        pk = league_pk(self.provider, dto.provider_league_id)
        league = db.get(League, pk)
        if league is None:
            league = League(
                id=pk,
                provider=self.provider,
                provider_league_id=dto.provider_league_id,
                name=dto.name,
            )
            db.add(league)
        league.name = dto.name
        league.country = dto.country
        league.kind = dto.kind
        league.current_season = dto.current_season
        league.cov_live_stats = dto.cov_live_stats
        league.cov_corners = dto.cov_corners
        league.cov_dangerous_attacks = dto.cov_dangerous_attacks
        league.cov_xg = dto.cov_xg
        league.coverage_notes = dto.coverage_notes
        league.verified_at = _now()
        return league

    def _upsert_team(self, db: Session, provider_id: str, name: str) -> Team:
        db.flush()
        pk = team_pk(self.provider, provider_id)
        team = db.get(Team, pk)
        if team is None:
            team = Team(id=pk, provider=self.provider, provider_team_id=provider_id, name=name)
            db.add(team)
        else:
            team.name = name
        return team

    # --- maclar ---
    def upsert_live_fixture(self, db: Session, fx: LiveFixture) -> Match:
        db.flush()
        lpk = league_pk(self.provider, fx.league_provider_id)
        league = db.get(League, lpk)
        if league is None:
            league = League(
                id=lpk,
                provider=self.provider,
                provider_league_id=fx.league_provider_id,
                name=fx.league_name,
                country=fx.league_country,
                kind="league",
                current_season=fx.season,
            )
            db.add(league)

        home = self._upsert_team(db, fx.home.provider_team_id, fx.home.name)
        away = self._upsert_team(db, fx.away.provider_team_id, fx.away.name)

        pk = match_pk(self.provider, fx.provider_fixture_id)
        match = db.get(Match, pk)
        if match is None:
            match = Match(
                id=pk,
                provider=self.provider,
                provider_fixture_id=fx.provider_fixture_id,
                league_id=lpk,
                home_team_id=home.id,
                away_team_id=away.id,
            )
            db.add(match)
        match.league_id = lpk
        match.home_team_id = home.id
        match.away_team_id = away.id
        match.season = fx.season
        match.kickoff_at = fx.kickoff_at
        match.status_short = fx.status_short
        match.status_long = fx.status_long
        match.elapsed_minute = fx.elapsed_minute
        match.home_goals = fx.home_goals
        match.away_goals = fx.away_goals
        match.last_updated_at = _now()
        return match

    # --- istatistikler ---
    def apply_statistics(self, db: Session, match: Match, stats: FixtureStatistics) -> None:
        if not stats.available or not stats.stats:
            return
        for ts in stats.stats:
            row = db.execute(
                select(MatchStat).where(
                    MatchStat.match_id == match.id,
                    MatchStat.side == ts.side,
                    MatchStat.period == "live",
                )
            ).scalar_one_or_none()
            if row is None:
                row = MatchStat(match_id=match.id, side=ts.side, period="live")
                db.add(row)
            row.shots_total = ts.shots_total
            row.shots_on = ts.shots_on
            row.shots_off = ts.shots_off
            row.shots_blocked = ts.shots_blocked
            row.corners = ts.corners
            row.dangerous_attacks = ts.dangerous_attacks
            row.possession = ts.possession
            row.yellow_cards = ts.yellow_cards
            row.red_cards = ts.red_cards
            row.xg = ts.xg
            row.source = stats.source
            row.updated_at = _now()

    def apply_events(self, db: Session, match: Match, events: list[FixtureEvent]) -> None:
        seen: set[str] = set()
        for ev in events:
            if ev.provider_event_id in seen:
                continue
            seen.add(ev.provider_event_id)
            row = db.get(MatchEvent, ev.provider_event_id)
            if row is None:
                row = MatchEvent(id=ev.provider_event_id, match_id=match.id)
                db.add(row)
            row.match_id = match.id
            row.minute = ev.minute
            row.extra_minute = ev.extra_minute
            row.type = ev.type
            row.detail = ev.detail
            row.side = ev.side
            row.player = ev.player
            row.assist = ev.assist
            row.comments = ev.comments

    # --- veri kalitesi ---
    def assess_quality(self, match: Match, stats_by_side: dict[str, MatchStat | None]) -> str:
        home = stats_by_side.get("home")
        away = stats_by_side.get("away")
        if home is None and away is None:
            return "missing"
        if home is None or away is None:
            return "partial"
        # Tutarlilik: possession toplami ~100 olmali
        if home.possession is not None and away.possession is not None:
            if abs((home.possession + away.possession) - 100) > 5:
                return "conflicting"
        # Temel sayim alanlari dolu mu?
        core = [home.shots_total, away.shots_total, home.corners, away.corners]
        if any(v is None for v in core):
            return "partial"
        return "good"
