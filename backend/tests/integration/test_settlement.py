from datetime import datetime, timezone

from sqlalchemy import select

from app.eval.settlement import settle_match
from app.ingest.normalizer import Normalizer
from app.models import MatchEvent, Prediction, PredictionOutcome, StatSnapshot
from app.providers.base import LeagueDTO, LiveFixture, TeamRef


def _finished_match(db, *, hg=1, ag=0, minute=90, fid="3001"):
    n = Normalizer("fixture-test")
    n.upsert_league(db, LeagueDTO("203", "Super Lig", "Turkey", "league", 2025))
    fx = LiveFixture(
        provider_fixture_id=fid, league_provider_id="203", league_name="Super Lig",
        league_country="Turkey", season=2025, home=TeamRef("10", "Ev"), away=TeamRef("20", "Dep"),
        kickoff_at=datetime(2026, 1, 1, tzinfo=timezone.utc), status_short="FT",
        status_long="Match Finished", elapsed_minute=minute, home_goals=hg, away_goals=ag,
    )
    m = n.upsert_live_fixture(db, fx)
    db.commit()
    return m


def _goal(db, match, minute, side="home", eid=None):
    db.add(MatchEvent(id=eid or f"{match.id}:g{minute}{side}", match_id=match.id, minute=minute,
                      type="Goal", detail="Normal Goal", side=side, player="X"))


def _pred(db, match, market, *, minute=20, target="goal", prob=0.5, threshold=None, horizon=None):
    p = Prediction(
        match_id=match.id, minute_at_prediction=minute, score_home=match.home_goals, score_away=match.away_goals,
        target=target, market=market, horizon_minutes=horizon, threshold=threshold, probability=prob,
        model_name="test", model_version="1.0.0", data_quality="good", provider="fixture-test",
    )
    db.add(p)
    db.commit()
    return p


def _outcome(db, pred, match):
    settle_match(db, match)
    db.refresh(pred)
    return pred.outcome


def test_goal_next_5_hit(db):
    m = _finished_match(db, hg=2, ag=0)
    _goal(db, m, 23)
    db.commit()
    p = _pred(db, m, "goal_next_5_min", minute=20)
    o = _outcome(db, p, m)
    assert o is not None and o.actual == 1 and o.evaluation_status == "hit"


def test_goal_next_5_miss(db):
    m = _finished_match(db, hg=1, ag=0)
    _goal(db, m, 30)  # pencere disinda
    db.commit()
    p = _pred(db, m, "goal_next_5_min", minute=20)
    o = _outcome(db, p, m)
    assert o.actual == 0 and o.evaluation_status == "miss"


def test_total_goals_over_settles(db):
    m = _finished_match(db, hg=3, ag=1)
    db.commit()
    p = _pred(db, m, "goals_total_over_2_5", target="goal", minute=10)
    o = _outcome(db, p, m)
    assert o.actual == 1


def test_next_goal_void_when_no_more_goals(db):
    m = _finished_match(db, hg=1, ag=0)
    p = _pred(db, m, "goal_next_home", minute=50)
    o = _outcome(db, p, m)
    assert o.actual is None and o.evaluation_status == "void"


def test_corner_window_from_snapshots(db):
    m = _finished_match(db, hg=0, ag=0)
    for side, c20, c30 in [("home", 2, 4), ("away", 1, 2)]:
        db.add(StatSnapshot(match_id=m.id, side=side, minute=20, corners=c20))
        db.add(StatSnapshot(match_id=m.id, side=side, minute=30, corners=c30))
    db.commit()
    p = _pred(db, m, "corner_next_10_min", target="corner", minute=20)
    o = _outcome(db, p, m)
    assert o.actual == 1 and o.evaluation_status == "hit"


def test_corner_total_over_settles(db):
    m = _finished_match(db, hg=1, ag=1)
    db.add(StatSnapshot(match_id=m.id, side="home", minute=88, corners=6))
    db.add(StatSnapshot(match_id=m.id, side="away", minute=88, corners=5))
    db.commit()
    p = _pred(db, m, "corners_total_over_9_5", target="corner", minute=60)
    o = _outcome(db, p, m)
    assert o.actual == 1  # 6+5=11 > 9.5


def test_unresolved_when_not_finished_and_window_not_reached(db):
    m = _finished_match(db, hg=0, ag=0, minute=30, fid="3002")
    m.status_short = "1H"
    db.commit()
    p = _pred(db, m, "goal_next_15_min", minute=25)
    settle_match(db, m)
    db.refresh(p)
    assert p.outcome is None  # 25+15=40 > 30, henuz cozulmez


def test_corner_unresolved_without_snapshots(db):
    m = _finished_match(db, hg=0, ag=0)
    p = _pred(db, m, "corner_next_10_min", target="corner", minute=20)
    o = _outcome(db, p, m)
    assert o is None or o.evaluation_status == "unresolved"
