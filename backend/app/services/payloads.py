"""Canli ve gunluk mac listesi yanitlarini uretir.

Ayni mantigi hem HTTP endpoint'leri hem de arka plan gorevi kullanir; boylece
pahali model hesaplari bir kez yapilip kisa sureli onbellekten servis edilir.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ingest.live import LIVE_SHORT_STATUSES, NOT_STARTED
from app.models import League, Match, Prediction
from app.services.match_view import key_markets, serialize_match
from app.services.prediction_service import run_models
from app.timeutil import in_day, local_today


def _live_query(db: Session):
    return db.execute(
        select(Match).where(Match.status_short.in_(list(LIVE_SHORT_STATUSES)))
    ).scalars().all()


def _prediction_payload(db: Session, match: Match) -> dict:
    if match.status_short in LIVE_SHORT_STATUSES:
        bundle = run_models(db, match)
        goal_keys = key_markets(bundle.goal)
        corner_keys = key_markets(bundle.corner)
        return {
            "goal_sufficient": bundle.goal.sufficient,
            "corner_sufficient": bundle.corner.sufficient,
            "goal_insufficient_reason": bundle.goal.insufficient_reason,
            "corner_insufficient_reason": bundle.corner.insufficient_reason,
            "goal_confidence": bundle.goal.confidence,
            "corner_confidence": bundle.corner.confidence,
            "goal": goal_keys,
            "corner": corner_keys,
            "source": "live",
            "as_of_minute": bundle.features.minute,
            "baseline": {
                "goal_source": bundle.baseline.source,
                "corner_source": bundle.baseline.source,
                "sample_matches": bundle.baseline.sample_matches,
                "note": bundle.baseline.note,
            },
        }
    if match.status_short not in NOT_STARTED:
        history = (
            db.query(Prediction)
            .filter(Prediction.match_id == match.id)
            .order_by(Prediction.created_at.desc())
            .all()
        )
        if history:
            def latest_map(target: str) -> tuple[dict[str, float], int | None]:
                target_rows = [r for r in history if r.target == target]
                if not target_rows:
                    return {}, None
                minute = max((r.minute_at_prediction or 0) for r in target_rows)
                rows = [r for r in target_rows if (r.minute_at_prediction or 0) == minute]
                return {r.market: r.probability for r in rows}, minute

            goal_map, goal_minute = latest_map("goal")
            corner_map, corner_minute = latest_map("corner")
            if goal_map or corner_map:
                minute = max(goal_minute or 0, corner_minute or 0)
                return {
                    "goal_sufficient": bool(goal_map),
                    "corner_sufficient": bool(corner_map),
                    "goal_insufficient_reason": None if goal_map else "Kayitli tahmin yok.",
                    "corner_insufficient_reason": None if corner_map else "Kayitli tahmin yok.",
                    "goal_confidence": 0.0,
                    "corner_confidence": 0.0,
                    "goal": goal_map,
                    "corner": corner_map,
                    "source": "history",
                    "as_of_minute": minute,
                    "baseline": {
                        "goal_source": "kayitli tahmin",
                        "corner_source": "kayitli tahmin",
                        "sample_matches": 0,
                        "note": f"Mac bitti; {minute}. dakikada kaydedilen tahminler gosteriliyor.",
                    },
                }

    reason = "Mac baslamadi; tahmin mac baslayinca uretilir." if match.status_short in NOT_STARTED else "Mac bitti; tahmin uretilmez."
    return {
        "goal_sufficient": False,
        "corner_sufficient": False,
        "goal_insufficient_reason": reason,
        "corner_insufficient_reason": reason,
        "goal_confidence": 0.0,
        "corner_confidence": 0.0,
        "goal": {},
        "corner": {},
        "source": "none",
        "as_of_minute": None,
        "baseline": {
            "goal_source": "—",
            "corner_source": "—",
            "sample_matches": 0,
            "note": reason,
        },
    }


def live_cache_key(
    league: str | None = None,
    minute_min: int | None = None,
    minute_max: int | None = None,
    min_goal_prob: float | None = None,
    min_corner_prob: float | None = None,
    data_quality: str | None = None,
) -> str:
    return f"live:{league}:{minute_min}:{minute_max}:{min_goal_prob}:{min_corner_prob}:{data_quality}"


def day_cache_key(date: str) -> str:
    return f"day:{date}"


def warm_payload_cache(db: Session) -> None:
    """Arka plan turundan sonra liste yanitlarini onbellege alir.

    Boylece kullanici istegi pahali model hesabini beklemez.
    """
    from app.services import response_cache

    response_cache.put(live_cache_key(), build_live(db))
    date = local_today().isoformat()
    response_cache.put(day_cache_key(date), build_day(db, date))


def build_live(
    db: Session,
    *,
    league: str | None = None,
    minute_min: int | None = None,
    minute_max: int | None = None,
    min_goal_prob: float | None = None,
    min_corner_prob: float | None = None,
    data_quality: str | None = None,
) -> dict:
    out = []
    for match in _live_query(db):
        league_obj = db.get(League, match.league_id)
        if league and league not in (match.league_id, league_obj.provider_league_id if league_obj else None):
            continue
        if minute_min is not None and (match.elapsed_minute or 0) < minute_min:
            continue
        if minute_max is not None and (match.elapsed_minute or 999) > minute_max:
            continue
        if data_quality and match.data_quality != data_quality:
            continue

        item = serialize_match(db, match, include_stats=True)
        item["predictions"] = _prediction_payload(db, match)
        goal_keys = item["predictions"].get("goal") or {}
        corner_keys = item["predictions"].get("corner") or {}
        g10 = goal_keys.get("goal_next_10_min")
        c10 = corner_keys.get("corner_next_10_min")
        if min_goal_prob is not None and (g10 is None or g10 < min_goal_prob):
            continue
        if min_corner_prob is not None and (c10 is None or c10 < min_corner_prob):
            continue
        out.append(item)

    out.sort(key=lambda x: x["minute"] or 0, reverse=True)
    return {"count": len(out), "matches": out}


def build_day(db: Session, date: str) -> dict:
    out = []
    for match in db.execute(select(Match).order_by(Match.kickoff_at)).scalars().all():
        if not in_day(match.kickoff_at, date):
            continue
        item = serialize_match(db, match, include_stats=True)
        item["predictions"] = _prediction_payload(db, match)
        out.append(item)
    out.sort(key=lambda x: x["kickoff_at"] or "")
    return {"count": len(out), "matches": out}
