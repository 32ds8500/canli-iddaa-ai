"""FotMob saglayicisi testleri (ag yok; sahte istemci)."""
from __future__ import annotations

import httpx

from app.providers.fotmob import FOTMOB_LEAGUE_IDS, FotMobProvider

MATCHES_PAYLOAD = {
    "leagues": [
        {
            "id": 71,
            "ccode": "TUR",
            "name": "Super Lig",
            "matches": [
                {
                    "id": 111,
                    "home": {"id": 1, "name": "Ev", "score": 1},
                    "away": {"id": 2, "name": "Dep", "score": 0},
                    "status": {
                        "utcTime": "2026-10-19T17:00:00.000Z",
                        "started": True,
                        "finished": False,
                        "cancelled": False,
                        "halfs": {"firstHalfStarted": "19.10.2026 20:00:00"},
                    },
                }
            ],
        },
        {
            "id": 47,
            "ccode": "ENG",
            "name": "Premier League",
            "matches": [],
        },
    ]
}

DETAIL_PAYLOAD = {
    "content": {
        "stats": {
            "Periods": {
                "All": {
                    "stats": [
                        {
                            "title": "Top stats",
                            "stats": [
                                {"key": "BallPossesion", "stats": [60, 40]},
                                {"key": "expected_goals", "stats": ["1.20", "0.40"]},
                                {"key": "total_shots", "stats": [12, 5]},
                                {"key": "ShotsOnTarget", "stats": [5, 1]},
                                {"key": "corners", "stats": [7, 2]},
                                {"key": "yellow_cards", "stats": [1, 3]},
                                {"key": "red_cards", "stats": [0, 1]},
                            ],
                        }
                    ]
                }
            }
        },
        "matchFacts": {
            "events": {
                "events": [
                    {
                        "eventId": 9,
                        "time": 23,
                        "type": "Goal",
                        "isHome": True,
                        "player": {"name": "Oyuncu"},
                        "goalDescription": "Header",
                    }
                ]
            }
        },
    }
}


def make_provider() -> FotMobProvider:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/api/data/matches"):
            return httpx.Response(200, json=MATCHES_PAYLOAD)
        if path.endswith("/api/data/matchDetails"):
            return httpx.Response(200, json=DETAIL_PAYLOAD)
        return httpx.Response(404, json={})

    client = httpx.Client(transport=httpx.MockTransport(handler), base_url="https://www.fotmob.com")
    return FotMobProvider(client=client)


def test_league_mapping_covers_all_targets() -> None:
    assert set(FOTMOB_LEAGUE_IDS) == {"203", "135", "140", "61", "2", "3", "848"}
    provider = make_provider()
    assert provider.map_target_league_ids(["203", "2"]) == ["71", "943230"]


def test_live_fixtures_filters_to_target_leagues() -> None:
    provider = make_provider()
    fixtures = provider.get_live_fixtures()
    assert len(fixtures) == 1
    fx = fixtures[0]
    assert fx.provider_fixture_id == "111"
    assert fx.league_provider_id == "71"
    assert fx.home.name == "Ev"
    assert fx.status_short in {"1H", "HT", "2H"}


def test_statistics_parse_real_shape() -> None:
    provider = make_provider()
    stats = provider.get_fixture_statistics("111")
    assert stats.available is True
    home, away = stats.stats
    assert home.possession == 60 and away.possession == 40
    assert home.shots_total == 12 and away.shots_total == 5
    assert home.corners == 7 and away.corners == 2
    assert home.xg == 1.2 and away.xg == 0.4
    assert home.red_cards == 0 and away.red_cards == 1


def test_events_parse_real_shape() -> None:
    provider = make_provider()
    events = provider.get_fixture_events("111")
    assert len(events) == 1
    ev = events[0]
    assert ev.minute == 23
    assert ev.type == "Goal"
    assert ev.side == "home"
    assert ev.player == "Oyuncu"
