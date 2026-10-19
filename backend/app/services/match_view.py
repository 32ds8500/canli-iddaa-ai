"""Mac gorunum yardimcilari (API serilestirme)."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.engines.types import EngineResult
from app.ingest.live import LiveIngestService
from app.models import League, Match, MatchStat, Team


def _stat_dict(row: MatchStat | None) -> dict | None:
    if row is None:
        return None
    return {
        "shots_total": row.shots_total,
        "shots_on": row.shots_on,
        "shots_off": row.shots_off,
        "shots_blocked": row.shots_blocked,
        "corners": row.corners,
        "dangerous_attacks": row.dangerous_attacks,
        "possession": row.possession,
        "yellow_cards": row.yellow_cards,
        "red_cards": row.red_cards,
        "xg": row.xg,
        "source": row.source,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def latest_stats(db: Session, match_id: str) -> dict[str, MatchStat | None]:
    rows = db.execute(select(MatchStat).where(MatchStat.match_id == match_id)).scalars().all()
    out: dict[str, MatchStat | None] = {"home": None, "away": None}
    for r in rows:
        cur = out.get(r.side)
        if cur is None or (r.updated_at and cur.updated_at and r.updated_at >= cur.updated_at):
            out[r.side] = r
    return out


def key_markets(result: EngineResult) -> dict[str, float]:
    """Motorun urettigi tum marketleri (market -> olasilik) dondurur."""
    return {p.market: p.probability for p in result.predictions}


def serialize_match(db: Session, match: Match, *, include_stats: bool = True) -> dict:
    league = db.get(League, match.league_id)
    home = db.get(Team, match.home_team_id)
    away = db.get(Team, match.away_team_id)
    stats = latest_stats(db, match.id) if include_stats else {}
    data = {
        "id": match.id,
        "provider": match.provider,
        "fixture_id": match.provider_fixture_id,
        "league": {
            "id": match.league_id,
            "name": league.name if league else None,
            "country": league.country if league else None,
            "kind": league.kind if league else None,
            "cov_live_stats": league.cov_live_stats if league else None,
            "cov_corners": league.cov_corners if league else None,
            "cov_dangerous_attacks": league.cov_dangerous_attacks if league else None,
            "cov_xg": league.cov_xg if league else None,
        },
        "home": {"id": match.home_team_id, "name": home.name if home else None},
        "away": {"id": match.away_team_id, "name": away.name if away else None},
        "kickoff_at": match.kickoff_at.isoformat() if match.kickoff_at else None,
        "status": {"short": match.status_short, "long": match.status_long},
        "minute": match.elapsed_minute,
        "score": {"home": match.home_goals, "away": match.away_goals},
        "data_quality": match.data_quality,
        "data_age_seconds": LiveIngestService.compute_data_age_seconds(match),
        "last_updated_at": match.last_updated_at.isoformat() if match.last_updated_at else None,
    }
    if include_stats:
        data["stats"] = {"home": _stat_dict(stats.get("home")), "away": _stat_dict(stats.get("away"))}
    return data
