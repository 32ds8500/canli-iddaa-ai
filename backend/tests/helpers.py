"""Test yardimcilari."""
from __future__ import annotations

from app.engines.features import MatchFeatures, TeamWindow


def make_features(
    *,
    minute: int = 30,
    score_home: int = 0,
    score_away: int = 0,
    home_possession: int | None = 55,
    away_possession: int | None = 45,
    home_red: int = 0,
    away_red: int = 0,
    has_live_stats: bool = True,
    data_quality: str = "good",
    corners_home: int = 0,
    corners_away: int = 0,
    shots_home: int = 0,
    shots_away: int = 0,
    windows_available: bool = True,
    w10_home_shots_on: int = 0,
    w10_away_shots_on: int = 0,
    w10_home_corners: int = 0,
    w10_away_corners: int = 0,
    w10_home_da: int = 0,
    w10_away_da: int = 0,
) -> MatchFeatures:
    def tw(side: str) -> TeamWindow:
        if not windows_available:
            return TeamWindow(available=False)
        if side == "home":
            return TeamWindow(
                shots=w10_home_shots_on, shots_on=w10_home_shots_on,
                corners=w10_home_corners, dangerous_attacks=w10_home_da, available=True,
            )
        return TeamWindow(
            shots=w10_away_shots_on, shots_on=w10_away_shots_on,
            corners=w10_away_corners, dangerous_attacks=w10_away_da, available=True,
        )

    windows = {f"last_{w}": {"home": tw("home"), "away": tw("away")} for w in (5, 10, 15)}
    return MatchFeatures(
        provider="fixture-test",
        league_provider_id="203",
        minute=minute,
        remaining_minutes=max(0, 90 - minute),
        score_home=score_home,
        score_away=score_away,
        total_goals=score_home + score_away,
        goal_diff=score_home - score_away,
        home_possession=home_possession,
        away_possession=away_possession,
        current_corners_home=corners_home,
        current_corners_away=corners_away,
        current_shots_home=shots_home,
        current_shots_away=shots_away,
        current_xg_home=None,
        current_xg_away=None,
        home_red_cards=home_red,
        away_red_cards=away_red,
        has_live_stats=has_live_stats,
        data_quality=data_quality,
        data_age_seconds=10,
        baseline_source="prior",
        baseline_note=None,
        windows=windows,
        pressure_home=0.0,
        pressure_away=0.0,
    )
