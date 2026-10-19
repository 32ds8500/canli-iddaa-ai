"""Ozellik uretimi: macin mevcut durumundan model girdileri.

Kayan pencere (son 5/10/15 dk) degisimleri stat_snapshots tablosundan
kumulatif fark ile hesaplanir. Yeterli gecmis anlik goruntu yoksa pencere
'mevcut degil' olarak isaretlenir; uydurulmaz.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.engines.baselines import Baseline, get_baseline
from app.models import Match, MatchStat, StatSnapshot

REGULATION_MINUTES = 90
WINDOWS = (5, 10, 15)


@dataclass
class TeamWindow:
    shots: int | None = None
    shots_on: int | None = None
    corners: int | None = None
    dangerous_attacks: int | None = None
    available: bool = False


@dataclass
class MatchFeatures:
    provider: str
    league_provider_id: str
    minute: int
    remaining_minutes: int
    score_home: int
    score_away: int
    total_goals: int
    goal_diff: int
    home_possession: int | None
    away_possession: int | None
    current_corners_home: int
    current_corners_away: int
    current_shots_home: int
    current_shots_away: int
    current_xg_home: float | None
    current_xg_away: float | None
    home_red_cards: int
    away_red_cards: int
    has_live_stats: bool
    data_quality: str
    data_age_seconds: int | None
    baseline_source: str
    baseline_note: str | None
    windows: dict[str, dict[str, TeamWindow]] = field(default_factory=dict)
    pressure_home: float = 0.0
    pressure_away: float = 0.0
    recent_goal_home: int = 0
    recent_goal_away: int = 0

    def to_jsonable(self) -> dict:
        data = asdict(self)
        return data


def _snapshot_at_or_before(snaps: list[StatSnapshot], target_minute: int) -> StatSnapshot | None:
    best: StatSnapshot | None = None
    for s in snaps:
        if s.minute <= target_minute:
            if best is None or s.minute > best.minute:
                best = s
    return best


def _window_value(
    latest: StatSnapshot, snaps: list[StatSnapshot], window: int, attr: str
) -> tuple[int | None, bool]:
    cur = getattr(latest, attr)
    base = _snapshot_at_or_before(snaps, latest.minute - window)
    if base is None or cur is None:
        return None, False
    base_val = getattr(base, attr)
    if base_val is None:
        return None, False
    delta = cur - base_val
    return max(0, delta), True


def _latest_stats(db: Session, match_id: str) -> dict[str, MatchStat]:
    rows = db.execute(select(MatchStat).where(MatchStat.match_id == match_id)).scalars().all()
    out: dict[str, MatchStat] = {}
    for r in rows:
        cur = out.get(r.side)
        if cur is None or (r.updated_at and cur.updated_at and r.updated_at >= cur.updated_at):
            out[r.side] = r
    return out


def _compute_windows(db: Session, match_id: str) -> dict[str, dict[str, TeamWindow]]:
    snaps_all = db.execute(
        select(StatSnapshot).where(StatSnapshot.match_id == match_id).order_by(StatSnapshot.minute)
    ).scalars().all()
    by_side: dict[str, list[StatSnapshot]] = {"home": [], "away": []}
    for s in snaps_all:
        by_side.setdefault(s.side, []).append(s)

    result: dict[str, dict[str, TeamWindow]] = {}
    for window in WINDOWS:
        per_side: dict[str, TeamWindow] = {}
        for side in ("home", "away"):
            snaps = sorted(by_side.get(side, []), key=lambda x: x.minute)
            if not snaps:
                per_side[side] = TeamWindow(available=False)
                continue
            latest = snaps[-1]
            tw = TeamWindow()
            vals = []
            for attr in ("shots_total", "shots_on", "corners", "dangerous_attacks"):
                val, ok = _window_value(latest, snaps, window, attr)
                setattr(tw, {"shots_total": "shots", "shots_on": "shots_on",
                             "corners": "corners", "dangerous_attacks": "dangerous_attacks"}[attr], val)
                vals.append(ok)
            tw.available = any(vals)
            per_side[side] = tw
        result[f"last_{window}"] = per_side
    return result


def compute_features(db: Session, match: Match) -> MatchFeatures:
    stats = _latest_stats(db, match.id)
    home = stats.get("home")
    away = stats.get("away")
    has_live_stats = home is not None and away is not None

    league = match.league if match.league else None
    provider_league_id = league.provider_league_id if league else ""
    baseline: Baseline = get_baseline(db, match.provider, provider_league_id)

    minute = max(0, min(95, match.elapsed_minute or 0))
    remaining = max(0, REGULATION_MINUTES - minute)

    windows = _compute_windows(db, match.id)

    # Basinc indeksi (son 10 dk): isabetli sut ve tehlikeli atak agirlikli
    def pressure(side: str) -> float:
        tw = windows.get("last_10", {}).get(side)
        if tw is None or not tw.available:
            return 0.0
        shots_on = tw.shots_on or 0
        da = tw.dangerous_attacks or 0
        return round(2.0 * shots_on + 0.5 * da, 3)

    now = datetime.now(timezone.utc)
    age = None
    if match.last_updated_at is not None:
        ref = match.last_updated_at
        if ref.tzinfo is None:
            ref = ref.replace(tzinfo=timezone.utc)
        age = int((now - ref).total_seconds())

    return MatchFeatures(
        provider=match.provider,
        league_provider_id=provider_league_id,
        minute=minute,
        remaining_minutes=remaining,
        score_home=match.home_goals or 0,
        score_away=match.away_goals or 0,
        total_goals=(match.home_goals or 0) + (match.away_goals or 0),
        goal_diff=(match.home_goals or 0) - (match.away_goals or 0),
        home_possession=home.possession if home else None,
        away_possession=away.possession if away else None,
        current_corners_home=(home.corners if home and home.corners is not None else 0),
        current_corners_away=(away.corners if away and away.corners is not None else 0),
        current_shots_home=(home.shots_total if home and home.shots_total is not None else 0),
        current_shots_away=(away.shots_total if away and away.shots_total is not None else 0),
        current_xg_home=(home.xg if home else None),
        current_xg_away=(away.xg if away else None),
        home_red_cards=(home.red_cards if home and home.red_cards is not None else 0),
        away_red_cards=(away.red_cards if away and away.red_cards is not None else 0),
        has_live_stats=has_live_stats,
        data_quality=match.data_quality,
        data_age_seconds=age,
        baseline_source=baseline.source,
        baseline_note=baseline.note,
        windows=windows,
        pressure_home=pressure("home"),
        pressure_away=pressure("away"),
    )
