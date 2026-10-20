"""Mac oncesi onizleme: son maclar, form, karsilikli gecmis ve Poisson tahmini.

Yalnizca gercek mac sonuclari kullanilir. Model, takimlarin son maclardaki
hucum/savunma verimliligini lig ortalamasina gore olceklendirip Poisson
dagilimi uretir; cok az veri varsa lig ortalamasina dogru kucultulur.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any

from app.providers.base import FootballProvider

LEAGUE_AVG_GOALS = 1.35
BASE_HOME_GOALS = 1.55
BASE_AWAY_GOALS = 1.20
DECAY = 0.85
SHRINK = 4.0
MAX_GOALS = 10
FORM_LIMIT = 10
H2H_LIMIT = 6

_FRIENDLY_MARKERS = ("friendl", "hazirlik", "amichevole", "freundschaft")


def _is_friendly(name: str) -> bool:
    low = (name or "").lower()
    return any(m in low for m in _FRIENDLY_MARKERS)


def _score(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _usable(m: dict) -> bool:
    return bool(m.get("finished")) and not m.get("cancelled") and not _is_friendly(m.get("tournament", ""))


def _weighted_mean(values: list[float]) -> tuple[float, float]:
    total_w = 0.0
    total = 0.0
    for i, v in enumerate(values):
        w = DECAY**i
        total += v * w
        total_w += w
    return total, total_w


def _team_rows(matches: list[dict], team_id: str, role: str | None = None) -> list[dict]:
    rows: list[dict] = []
    for m in matches:
        if not _usable(m):
            continue
        is_home = m.get("home_id") == team_id
        is_away = m.get("away_id") == team_id
        if not (is_home or is_away):
            continue
        if role == "home" and not is_home:
            continue
        if role == "away" and not is_away:
            continue
        gf = _score(m.get("home_goals") if is_home else m.get("away_goals"))
        ga = _score(m.get("away_goals") if is_home else m.get("home_goals"))
        if gf is None or ga is None:
            continue
        rows.append(
            {
                "id": m.get("id"),
                "kickoff": m.get("kickoff"),
                "home": is_home,
                "gf": gf,
                "ga": ga,
                "opponent": m.get("away_name") if is_home else m.get("home_name"),
                "opponent_id": m.get("away_id") if is_home else m.get("home_id"),
                "competition": m.get("tournament"),
            }
        )
    rows.sort(key=lambda r: r.get("kickoff") or "", reverse=True)
    return rows


def _summary(rows: list[dict], limit: int = FORM_LIMIT) -> dict:
    recent = rows[:limit]
    wins = sum(1 for r in recent if r["gf"] > r["ga"])
    draws = sum(1 for r in recent if r["gf"] == r["ga"])
    losses = sum(1 for r in recent if r["gf"] < r["ga"])
    played = len(recent)
    gf = sum(r["gf"] for r in recent)
    ga = sum(r["ga"] for r in recent)
    over25 = sum(1 for r in recent if r["gf"] + r["ga"] > 2.5)
    btts = sum(1 for r in recent if r["gf"] > 0 and r["ga"] > 0)
    form = []
    for r in recent:
        form.append("W" if r["gf"] > r["ga"] else "D" if r["gf"] == r["ga"] else "L")
    return {
        "played": played,
        "wins": wins,
        "draws": draws,
        "losses": losses,
        "gf": gf,
        "ga": ga,
        "avg_gf": round(gf / played, 2) if played else None,
        "avg_ga": round(ga / played, 2) if played else None,
        "over25_rate": round(over25 / played, 3) if played else None,
        "btts_rate": round(btts / played, 3) if played else None,
        "form": form,
        "recent": [
            {
                "date": (r.get("kickoff") or "")[:10],
                "home": r["home"],
                "opponent": r.get("opponent"),
                "score": f"{r['gf']}-{r['ga']}",
                "competition": r.get("competition"),
            }
            for r in recent[:5]
        ],
    }


def _team_profile(matches: list[dict], team_id: str, role: str) -> dict:
    split = _team_rows(matches, team_id, role)
    overall = _team_rows(matches, team_id)
    if len(split) >= 4:
        base = split[:8]
        basis = f"son {len(base)} {('ic saha' if role == 'home' else 'deplasman')} maci"
    else:
        base = overall[:FORM_LIMIT]
        basis = f"son {len(base)} mac (yeterli {('ic saha' if role == 'home' else 'deplasman')} verisi yok)"
    w_gf, w_n = _weighted_mean([float(r["gf"]) for r in base])
    w_ga, _ = _weighted_mean([float(r["ga"]) for r in base])

    def shrink(total: float, n: float) -> float:
        return (total + SHRINK * LEAGUE_AVG_GOALS) / (n + SHRINK)

    return {
        "attack": shrink(w_gf, w_n) / LEAGUE_AVG_GOALS,
        "defense": shrink(w_ga, w_n) / LEAGUE_AVG_GOALS,
        "basis": basis,
        "sample": len(base),
    }


def _poisson_markets(lh: float, la: float) -> dict:
    import math

    ph = [math.exp(-lh) * lh**k / math.factorial(k) for k in range(MAX_GOALS + 1)]
    pa = [math.exp(-la) * la**k / math.factorial(k) for k in range(MAX_GOALS + 1)]
    home = draw = away = over15 = over25 = over35 = btts = 0.0
    for i, pi in enumerate(ph):
        for j, pj in enumerate(pa):
            p = pi * pj
            total = i + j
            if i > j:
                home += p
            elif i == j:
                draw += p
            else:
                away += p
            if total > 1.5:
                over15 += p
            if total > 2.5:
                over25 += p
            if total > 3.5:
                over35 += p
            if i > 0 and j > 0:
                btts += p
    return {
        "home_win": round(home, 4),
        "draw": round(draw, 4),
        "away_win": round(away, 4),
        "dc_1x": round(home + draw, 4),
        "dc_12": round(home + away, 4),
        "dc_x2": round(draw + away, 4),
        "over_1_5": round(over15, 4),
        "over_2_5": round(over25, 4),
        "under_2_5": round(1 - over25, 4),
        "over_3_5": round(over35, 4),
        "btts": round(btts, 4),
    }


def _h2h(home_matches: list[dict], away_matches: list[dict], home_id: str, away_id: str) -> dict:
    seen: dict[str, dict] = {}
    for m in home_matches + away_matches:
        if not _usable(m):
            continue
        pair = {m.get("home_id"), m.get("away_id")}
        if pair != {home_id, away_id}:
            continue
        seen[m.get("id")] = m
    rows = sorted(seen.values(), key=lambda m: m.get("kickoff") or "", reverse=True)[:H2H_LIMIT]
    wins = draws = losses = 0
    items = []
    for m in rows:
        hg = _score(m.get("home_goals"))
        ag = _score(m.get("away_goals"))
        if hg is None or ag is None:
            continue
        home_is_current = m.get("home_id") == home_id
        gf, ga = (hg, ag) if home_is_current else (ag, hg)
        if gf > ga:
            wins += 1
        elif gf == ga:
            draws += 1
        else:
            losses += 1
        items.append(
            {
                "date": (m.get("kickoff") or "")[:10],
                "home": m.get("home_name"),
                "away": m.get("away_name"),
                "score": f"{hg}-{ag}",
                "competition": m.get("tournament"),
            }
        )
    return {
        "played": len(items),
        "wins": wins,
        "draws": draws,
        "losses": losses,
        "matches": items,
    }


def build_preview(
    provider: FootballProvider,
    home_id: str,
    away_id: str,
    home_name: str,
    away_name: str,
    provider_fixture_id: str | None = None,
) -> dict:
    home_matches = provider.get_team_matches(home_id)
    away_matches = provider.get_team_matches(away_id)
    h2h_matches: list[dict] = []
    if provider_fixture_id:
        try:
            h2h_matches = provider.get_h2h(provider_fixture_id)
        except Exception:  # noqa: BLE001 - H2H opsiyonel
            h2h_matches = []

    home_form = _summary(_team_rows(home_matches, home_id))
    away_form = _summary(_team_rows(away_matches, away_id))
    home_profile = _team_profile(home_matches, home_id, "home")
    away_profile = _team_profile(away_matches, away_id, "away")

    lh = home_profile["attack"] * away_profile["defense"] * BASE_HOME_GOALS
    la = away_profile["attack"] * home_profile["defense"] * BASE_AWAY_GOALS
    lh = max(0.35, min(3.6, lh))
    la = max(0.30, min(3.2, la))

    prediction = None
    if home_form["played"] and away_form["played"]:
        prediction = {
            "lambda_home": round(lh, 2),
            "lambda_away": round(la, 2),
            "markets": _poisson_markets(lh, la),
            "note": "Gecmis skorlara dayali istatistiksel tahmin; garanti degildir. Farkli liglerden takimlarda lig gucu farki modele sinirli yansir.",
        }
    return {
        "home": {"team_id": home_id, "name": home_name, **home_form, "basis": home_profile["basis"]},
        "away": {"team_id": away_id, "name": away_name, **away_form, "basis": away_profile["basis"]},
        "h2h": _h2h(h2h_matches or (home_matches + away_matches), [], home_id, away_id),
        "prediction": prediction,
    }


@dataclass
class PreviewTask:
    match_id: str
    home_id: str
    away_id: str
    home_name: str
    away_name: str
    provider_fixture_id: str | None = None


def build_previews(provider: FootballProvider, tasks: list[PreviewTask], workers: int = 4) -> dict[str, dict]:
    if not tasks:
        return {}
    out: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(
                build_preview,
                provider,
                t.home_id,
                t.away_id,
                t.home_name,
                t.away_name,
                t.provider_fixture_id,
            ): t.match_id
            for t in tasks
        }
        for future, match_id in futures.items():
            try:
                out[match_id] = future.result()
            except Exception:  # noqa: BLE001 - tek mac onizlemesi sayfayi dusurmesin
                continue
    return out
