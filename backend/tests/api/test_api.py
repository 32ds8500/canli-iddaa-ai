from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.api import deps
from app.db import get_db
from app.ingest.live import LiveIngestService
from app.main import app
from app.providers.base import (
    FixtureEvent,
    FixtureStatistics,
    LeagueDTO,
    LiveFixture,
    TeamRef,
    TeamStats,
)
from app.providers.fixture_provider import FixtureProvider

LEAGUE = LeagueDTO("203", "Super Lig", "Turkey", "league", 2025,
                   cov_live_stats=True, cov_corners=True, cov_dangerous_attacks=True, cov_xg=False)


def _live():
    return LiveFixture(
        provider_fixture_id="9001", league_provider_id="203", league_name="Super Lig",
        league_country="Turkey", season=2025, home=TeamRef("1", "Ev Takim"), away=TeamRef("2", "Dep Takim"),
        kickoff_at=datetime(2026, 1, 1, tzinfo=timezone.utc), status_short="2H",
        status_long="Second Half", elapsed_minute=60, home_goals=1, away_goals=1,
    )


def _stats():
    return FixtureStatistics(
        provider_fixture_id="9001", source="fixture-test", available=True,
        stats=[
            TeamStats("home", shots_total=10, shots_on=4, shots_off=4, shots_blocked=2, corners=4,
                      dangerous_attacks=30, possession=55, yellow_cards=1, red_cards=0),
            TeamStats("away", shots_total=7, shots_on=2, shots_off=3, shots_blocked=2, corners=3,
                      dangerous_attacks=22, possession=45, yellow_cards=2, red_cards=0),
        ],
    )


def _events():
    return [FixtureEvent("9001:0", 30, None, "Goal", "Normal Goal", "home", "A", None, None)]


def make_provider():
    return FixtureProvider(
        leagues=[LEAGUE], live=[_live()], stats={"9001": _stats()}, events={"9001": _events()}
    )


def make_client(db, provider):
    ingest = LiveIngestService(provider, ["203"])
    app.dependency_overrides[get_db] = lambda: (yield db)
    app.dependency_overrides[deps.get_provider_dep] = lambda: provider
    app.dependency_overrides[deps.get_ingest_dep] = lambda: ingest
    return TestClient(app)


def _clear():
    app.dependency_overrides.clear()


def test_health(db):
    client = make_client(db, make_provider())
    try:
        r = client.get("/api/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"
    finally:
        _clear()


def test_live_flow_and_predictions(db):
    provider = make_provider()
    client = make_client(db, provider)
    try:
        r = client.post("/api/matches/refresh-live")
        assert r.status_code == 200
        assert r.json()["refreshed"] == 1

        # Istatistik cekilmeden tahmin yeterli olmamali (durust davranis)
        r = client.get("/api/matches/live")
        data = r.json()
        assert data["count"] == 1
        assert data["matches"][0]["predictions"]["goal_sufficient"] is False

        # Istatistik cek -> artik yeterli ve tahminler kaydedilir
        r = client.post("/api/matches/enrich-watchlist", params={"limit": 1})
        assert r.status_code == 200
        r = client.get("/api/predictions")
        assert r.json()["count"] > 0

        r = client.get("/api/matches/live")
        data = r.json()
        assert data["count"] == 1
        match = data["matches"][0]
        assert match["home"]["name"] == "Ev Takim"
        assert match["predictions"]["goal_sufficient"] is True
        assert "goal_next_10_min" in match["predictions"]["goal"]

        mid = match["id"]
        r = client.post(f"/api/matches/{mid}/refresh")
        assert r.status_code == 200
        # Ayni dakika + model surumu icin mukerrer kayit olusturulmaz (sürüm korumasi)
        assert r.json()["current_predictions"]["goal"]["sufficient"] is True
        assert r.json()["predictions_created"] == 0

        r = client.get(f"/api/matches/{mid}")
        assert r.status_code == 200
        detail = r.json()
        assert detail["stats"]["home"]["corners"] == 4
        assert len(detail["prediction_history"]) > 0
        assert len(detail["events"]) == 1

        r = client.get("/api/predictions", params={"target": "corner"})
        assert r.status_code == 200
        assert r.json()["count"] > 0
    finally:
        _clear()


def test_leagues_endpoint(db):
    provider = make_provider()
    client = make_client(db, provider)
    try:
        client.post("/api/matches/refresh-live")
        r = client.get("/api/leagues")
        assert r.status_code == 200
        leagues = r.json()["leagues"]
        assert any(lg["provider_league_id"] == "203" for lg in leagues)
    finally:
        _clear()


def test_performance_endpoint_empty(db):
    provider = make_provider()
    client = make_client(db, provider)
    try:
        r = client.get("/api/performance", params={"dimension": "overall"})
        assert r.status_code == 200
        assert r.json()["segments"] == []
    finally:
        _clear()


def test_filter_by_min_goal_prob(db):
    provider = make_provider()
    client = make_client(db, provider)
    try:
        client.post("/api/matches/refresh-live")
        client.post("/api/matches/enrich-watchlist", params={"limit": 1})
        r = client.get("/api/matches/live", params={"min_goal_prob": 0.999})
        assert r.status_code == 200
        # cok yuksek esik -> buyuk olasilikla filtre bos
        assert r.json()["count"] == 0
    finally:
        _clear()
