"""Lig/takim taban cizgileri (baseline).

Baslangicta YAYINLANMIS LIG ORTALAMALARINA yaklasik onsel (prior) degerler
kullanilir; bunlar olculmus canli veri DEGILDIR ve 'prior' olarak
isaretlenir. Yeterli bitmis mac verisi toplandiginda degerler gercek
veriden TAHMIN edilir (source='estimated') ve prior otomatik devre disi kalir.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ingest.normalizer import league_pk
from app.models import Match, MatchStat

ESTIMATE_MIN_SAMPLE = 30


@dataclass
class Baseline:
    goals_per_match: float
    goals_home_share: float  # ev sahibinin toplam gollerdeki payi
    corners_per_match: float
    corners_home_share: float
    sample_matches: int
    source: str  # prior|estimated
    note: str | None = None


# Yaklasik yayinlanmis lig ortalamalari (PRIOR - olculmus canli veri degildir).
_PRIORS: dict[str, tuple[float, float, float]] = {
    # api_football league id: (gol/mac, ev-payi, korner/mac)
    "203": (2.9, 0.54, 9.6),   # Super Lig
    "135": (2.7, 0.54, 10.3),  # Serie A
    "140": (2.5, 0.55, 9.4),   # La Liga
    "61": (2.8, 0.55, 9.8),    # Ligue 1
    "2": (3.1, 0.53, 10.1),    # Sampiyonlar Ligi
    "3": (3.0, 0.53, 10.0),    # Avrupa Ligi
    "848": (3.0, 0.53, 10.4),  # Konferans Ligi
}
_DEFAULT_PRIOR = (2.7, 0.54, 10.0)


def prior_baseline(provider_league_id: str) -> Baseline:
    goals, home_share, corners = _PRIORS.get(provider_league_id, _DEFAULT_PRIOR)
    return Baseline(
        goals_per_match=goals,
        goals_home_share=home_share,
        corners_per_match=corners,
        corners_home_share=0.54,
        sample_matches=0,
        source="prior",
        note="Yayinlanmis lig ortalamalarina yaklasik onsel deger; olculmus canli veri degildir.",
    )


def estimate_baseline(db: Session, provider: str, provider_league_id: str) -> Baseline | None:
    """Veritabanindaki bitmis maclardan baseline tahmin eder."""
    lpk = league_pk(provider, provider_league_id)
    finished = db.execute(
        select(Match).where(Match.league_id == lpk, Match.status_short.in_(["FT", "AET", "PEN"]))
    ).scalars().all()
    goals_matches = [m for m in finished if m.home_goals is not None and m.away_goals is not None]
    if len(goals_matches) < ESTIMATE_MIN_SAMPLE:
        return None

    total_goals = sum(m.home_goals + m.away_goals for m in goals_matches)
    home_goals = sum(m.home_goals for m in goals_matches)
    goals_per_match = total_goals / len(goals_matches)
    home_share = (home_goals / total_goals) if total_goals else 0.54

    # Korner: her iki takimin istatistigi olan maclar
    corner_matches: list[tuple[int, int]] = []
    for m in finished:
        rows = {
            r.side: r
            for r in db.execute(select(MatchStat).where(MatchStat.match_id == m.id)).scalars()
        }
        h, a = rows.get("home"), rows.get("away")
        if h and a and h.corners is not None and a.corners is not None:
            corner_matches.append((h.corners, a.corners))
    if corner_matches:
        total_corners = sum(h + a for h, a in corner_matches)
        corners_per_match = total_corners / len(corner_matches)
        corners_home_share = sum(h for h, _ in corner_matches) / total_corners if total_corners else 0.54
    else:
        prior = prior_baseline(provider_league_id)
        corners_per_match = prior.corners_per_match
        corners_home_share = prior.corners_home_share

    return Baseline(
        goals_per_match=goals_per_match,
        goals_home_share=home_share,
        corners_per_match=corners_per_match,
        corners_home_share=corners_home_share,
        sample_matches=len(goals_matches),
        source="estimated",
        note=None,
    )


def get_baseline(db: Session, provider: str, provider_league_id: str) -> Baseline:
    estimated = estimate_baseline(db, provider, provider_league_id)
    return estimated or prior_baseline(provider_league_id)
