"""Tahminleri gercek mac sonuclariyla esleştirme (settlement).

Yalnizca kanit yeterli oldugunda sonuclandirir. Veri yetersizse 'unresolved'
birakir; uydurma sonuc uretmez.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Match, MatchEvent, MatchStat, Prediction, PredictionOutcome, StatSnapshot, utcnow

FINISHED = {"FT", "AET", "PEN"}


def _goal_events(db: Session, match_id: str) -> list[MatchEvent]:
    rows = db.execute(
        select(MatchEvent).where(MatchEvent.match_id == match_id, MatchEvent.type == "Goal")
    ).scalars().all()
    return [e for e in rows if e.minute is not None]


def _snapshots(db: Session, match_id: str) -> dict[str, list[StatSnapshot]]:
    rows = db.execute(select(StatSnapshot).where(StatSnapshot.match_id == match_id)).scalars().all()
    by_side: dict[str, list[StatSnapshot]] = {}
    for s in rows:
        by_side.setdefault(s.side, []).append(s)
    for v in by_side.values():
        v.sort(key=lambda x: x.minute)
    return by_side


def _cum_corners_at(snaps: dict[str, list[StatSnapshot]], minute: int, side: str | None = None) -> int | None:
    sides = [side] if side else ["home", "away"]
    total = 0
    for sd in sides:
        best = None
        for s in snaps.get(sd, []):
            if s.minute <= minute and s.corners is not None:
                best = s
        if best is None:
            return None
        total += best.corners
    return total


def _final_corners(db: Session, match: Match) -> tuple[int | None, int | None]:
    snaps = _snapshots(db, match.id)
    h = _cum_corners_at(snaps, 999, "home")
    a = _cum_corners_at(snaps, 999, "away")
    if h is not None and a is not None:
        return h, a
    rows = {r.side: r for r in db.execute(select(MatchStat).where(MatchStat.match_id == match.id)).scalars()}
    hh = rows["home"].corners if "home" in rows and rows["home"].corners is not None else None
    aa = rows["away"].corners if "away" in rows and rows["away"].corners is not None else None
    return hh, aa


def _resolve(pred: Prediction, match: Match, db: Session) -> tuple[int | None, str, str]:
    """(actual, status, detail) dondurur."""
    m = pred.minute_at_prediction or 0
    market = pred.market
    goals = _goal_events(db, match.id)
    finished = match.status_short in FINISHED
    now_minute = match.elapsed_minute if match.elapsed_minute is not None else (90 if finished else m)

    def goals_between(a_min: int, b_min: int) -> list[MatchEvent]:
        return [g for g in goals if g.minute is not None and a_min < g.minute <= b_min]

    detail = f"market={market}, t0={m}"
    if market.startswith("goal_next_") and market.endswith("_min"):
        horizon = int(market.split("_")[2])
        if not (finished or now_minute >= m + horizon):
            return None, "unresolved", detail
        evts = goals_between(m, m + horizon)
        return (1 if evts else 0), ("hit" if evts else "miss"), detail
    if market.startswith("goal_home_next_") and market.endswith("_min"):
        horizon = int(market.split("_")[3])
        if not (finished or now_minute >= m + horizon):
            return None, "unresolved", detail
        evts = [e for e in goals_between(m, m + horizon) if e.side == "home"]
        return (1 if evts else 0), ("hit" if evts else "miss"), detail
    if market.startswith("goal_away_next_") and market.endswith("_min"):
        horizon = int(market.split("_")[3])
        if not (finished or now_minute >= m + horizon):
            return None, "unresolved", detail
        evts = [e for e in goals_between(m, m + horizon) if e.side == "away"]
        return (1 if evts else 0), ("hit" if evts else "miss"), detail
    if market == "goal_rest_at_least_one":
        if not finished:
            return None, "unresolved", detail
        evts = goals_between(m, 200)
        return (1 if evts else 0), ("hit" if evts else "miss"), detail
    if market == "goal_home_rest":
        if not finished:
            return None, "unresolved", detail
        evts = [e for e in goals_between(m, 200) if e.side == "home"]
        return (1 if evts else 0), ("hit" if evts else "miss"), detail
    if market == "goal_away_rest":
        if not finished:
            return None, "unresolved", detail
        evts = [e for e in goals_between(m, 200) if e.side == "away"]
        return (1 if evts else 0), ("hit" if evts else "miss"), detail
    if market in ("goal_next_home", "goal_next_away"):
        if not finished:
            return None, "unresolved", detail
        evts = sorted(goals_between(m, 200), key=lambda e: e.minute or 0)
        if not evts:
            return None, "void", "Mac sonuna kadar gol olmadi; 'siradaki gol' cozumsuz."
        first = evts[0]
        is_home = first.side == "home"
        actual = 1 if (market == "goal_next_home") == is_home else 0
        return actual, ("hit" if actual == 1 else "miss"), f"ilk gol dk {first.minute} ({first.side})"
    if market.startswith("goals_total_over_"):
        if not finished:
            return None, "unresolved", detail
        th = float(market.replace("goals_total_over_", "").replace("_", "."))
        total = (match.home_goals or 0) + (match.away_goals or 0)
        actual = 1 if total > th else 0
        return actual, ("hit" if actual else "miss"), f"toplam gol {total}"
    # --- Korner ---
    if market.startswith("corner_next_") and market.endswith("_min"):
        horizon = int(market.split("_")[2])
        if not (finished or now_minute >= m + horizon):
            return None, "unresolved", detail
        snaps = _snapshots(db, match.id)
        c0 = _cum_corners_at(snaps, m)
        c1 = _cum_corners_at(snaps, m + horizon)
        if c0 is None or c1 is None:
            return None, "unresolved", "Korner anlik goruntusu yetersiz."
        actual = 1 if (c1 - c0) >= 1 else 0
        return actual, ("hit" if actual else "miss"), detail
    if market == "corner_rest_at_least_one":
        if not finished:
            return None, "unresolved", detail
        h, a = _final_corners(db, match)
        snaps = _snapshots(db, match.id)
        c0 = _cum_corners_at(snaps, m)
        if c0 is None or h is None:
            return None, "unresolved", "Korner verisi yetersiz."
        actual = 1 if (h + a - c0) >= 1 else 0
        return actual, ("hit" if actual else "miss"), detail
    if market.startswith("corners_total_over_"):
        if not finished:
            return None, "unresolved", detail
        th = float(market.replace("corners_total_over_", "").replace("_", "."))
        h, a = _final_corners(db, match)
        if h is None or a is None:
            return None, "unresolved", "Mac sonu korner verisi yok."
        actual = 1 if (h + a) > th else 0
        return actual, ("hit" if actual else "miss"), f"toplam korner {h + a}"
    if market.startswith("corners_home_over_"):
        if not finished:
            return None, "unresolved", detail
        th = float(market.replace("corners_home_over_", "").replace("_", "."))
        h, _ = _final_corners(db, match)
        if h is None:
            return None, "unresolved", "Ev sahibi korner verisi yok."
        actual = 1 if h > th else 0
        return actual, ("hit" if actual else "miss"), f"ev korner {h}"
    if market.startswith("corners_away_over_"):
        if not finished:
            return None, "unresolved", detail
        th = float(market.replace("corners_away_over_", "").replace("_", "."))
        _, a = _final_corners(db, match)
        if a is None:
            return None, "unresolved", "Deplasman korner verisi yok."
        actual = 1 if a > th else 0
        return actual, ("hit" if actual else "miss"), f"dep korner {a}"

    return None, "unresolved", f"Bilinmeyen market: {market}"


def settle_match(db: Session, match: Match) -> int:
    """Bir macin cozulmemis tahminlerini sonuclandirir. Guncellenen sayisini dondurur."""
    preds = db.execute(
        select(Prediction)
        .outerjoin(PredictionOutcome, PredictionOutcome.prediction_id == Prediction.id)
        .where(Prediction.match_id == match.id, PredictionOutcome.id.is_(None))
    ).scalars().all()

    updated = 0
    for pred in preds:
        actual, status, detail = _resolve(pred, match, db)
        if status == "unresolved":
            continue
        outcome = PredictionOutcome(
            prediction_id=pred.id,
            resolved_at=utcnow(),
            actual=actual,
            actual_detail=detail,
            evaluation_status=status,
        )
        db.add(outcome)
        updated += 1
    if updated:
        db.commit()
    return updated


def settle_finished_matches(db: Session) -> int:
    matches = db.execute(select(Match).where(Match.status_short.in_(list(FINISHED)))).scalars().all()
    total = 0
    for m in matches:
        total += settle_match(db, m)
    return total
