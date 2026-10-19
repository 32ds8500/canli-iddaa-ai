from datetime import datetime, timezone

from app.ingest.normalizer import Normalizer
from app.models import MatchStat
from app.providers.base import FixtureEvent, LeagueDTO, LiveFixture, TeamRef


def _fixture(fid="1001", status="1H", minute=30, hg=1, ag=0):
    return LiveFixture(
        provider_fixture_id=fid,
        league_provider_id="203",
        league_name="Super Lig",
        league_country="Turkey",
        season=2025,
        home=TeamRef("10", "Ev Takim"),
        away=TeamRef("20", "Deplasman Takim"),
        kickoff_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        status_short=status,
        status_long="First Half",
        elapsed_minute=minute,
        home_goals=hg,
        away_goals=ag,
    )


def test_upsert_match_idempotent(db):
    n = Normalizer("fixture-test")
    m1 = n.upsert_live_fixture(db, _fixture())
    db.commit()
    m2 = n.upsert_live_fixture(db, _fixture(minute=35, hg=1, ag=1))
    db.commit()
    assert m1.id == m2.id
    assert db.get(type(m1), m1.id).elapsed_minute == 35


def test_events_idempotent_and_unique(db):
    n = Normalizer("fixture-test")
    match = n.upsert_live_fixture(db, _fixture())
    db.commit()
    events = [
        FixtureEvent("ev1", 12, None, "Goal", "Normal Goal", "home", "A", None, None),
        FixtureEvent("ev1", 12, None, "Goal", "Normal Goal", "home", "A", None, None),
    ]
    n.apply_events(db, match, events)
    db.commit()
    from app.models import MatchEvent
    from sqlalchemy import select

    rows = db.execute(select(MatchEvent).where(MatchEvent.match_id == match.id)).scalars().all()
    assert len(rows) == 1


def test_quality_missing(db):
    n = Normalizer("fixture-test")
    match = n.upsert_live_fixture(db, _fixture())
    assert n.assess_quality(match, {"home": None, "away": None}) == "missing"


def test_quality_partial(db):
    n = Normalizer("fixture-test")
    match = n.upsert_live_fixture(db, _fixture())
    home = MatchStat(match_id=match.id, side="home", shots_total=5, corners=2, possession=55)
    assert n.assess_quality(match, {"home": home, "away": None}) == "partial"


def test_quality_conflicting_possession(db):
    n = Normalizer("fixture-test")
    match = n.upsert_live_fixture(db, _fixture())
    home = MatchStat(match_id=match.id, side="home", shots_total=5, corners=2, possession=70)
    away = MatchStat(match_id=match.id, side="away", shots_total=3, corners=1, possession=60)  # toplam 130
    assert n.assess_quality(match, {"home": home, "away": away}) == "conflicting"


def test_quality_good(db):
    n = Normalizer("fixture-test")
    match = n.upsert_live_fixture(db, _fixture())
    home = MatchStat(match_id=match.id, side="home", shots_total=5, corners=2, possession=55)
    away = MatchStat(match_id=match.id, side="away", shots_total=3, corners=1, possession=45)
    assert n.assess_quality(match, {"home": home, "away": away}) == "good"
