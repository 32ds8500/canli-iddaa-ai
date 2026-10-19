from datetime import datetime, timezone

from app.engines.features import compute_features
from app.ingest.normalizer import Normalizer
from app.models import MatchStat, StatSnapshot
from app.providers.base import LeagueDTO, LiveFixture, TeamRef


def _fixture():
    return LiveFixture(
        provider_fixture_id="2001",
        league_provider_id="203",
        league_name="Super Lig",
        league_country="Turkey",
        season=2025,
        home=TeamRef("10", "Ev"),
        away=TeamRef("20", "Dep"),
        kickoff_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        status_short="1H",
        status_long="First Half",
        elapsed_minute=30,
        home_goals=1,
        away_goals=0,
    )


def _setup(db, *, with_stats=True):
    n = Normalizer("fixture-test")
    n.upsert_league(db, LeagueDTO("203", "Super Lig", "Turkey", "league", 2025))
    match = n.upsert_live_fixture(db, _fixture())
    if with_stats:
        db.add(MatchStat(match_id=match.id, side="home", shots_total=6, shots_on=3, corners=3, possession=58,
                         updated_at=datetime.now(timezone.utc)))
        db.add(MatchStat(match_id=match.id, side="away", shots_total=2, shots_on=0, corners=1, possession=42,
                         updated_at=datetime.now(timezone.utc)))
        for minute, hc, ac in [(10, 1, 0), (20, 2, 1), (30, 3, 1)]:
            db.add(StatSnapshot(match_id=match.id, side="home", minute=minute, corners=hc,
                                shots_total=minute // 5, shots_on=minute // 10, dangerous_attacks=minute,
                                fired_at=datetime.now(timezone.utc)))
            db.add(StatSnapshot(match_id=match.id, side="away", minute=minute, corners=ac,
                                shots_total=minute // 10, shots_on=0, dangerous_attacks=minute // 2,
                                fired_at=datetime.now(timezone.utc)))
    db.commit()
    return match


def test_rolling_window_corner_deltas(db):
    match = _setup(db)
    feats = compute_features(db, match)
    assert feats.current_corners_home == 3
    assert feats.windows["last_10"]["home"].corners == 1
    assert feats.windows["last_15"]["home"].corners == 2
    assert feats.minute == 30
    assert feats.remaining_minutes == 60


def test_no_stats_marks_not_live(db):
    match = _setup(db, with_stats=False)
    feats = compute_features(db, match)
    assert feats.has_live_stats is False
    assert feats.windows["last_10"]["home"].available is False


def test_goal_diff_and_total(db):
    match = _setup(db)
    feats = compute_features(db, match)
    assert feats.goal_diff == 1
    assert feats.total_goals == 1
