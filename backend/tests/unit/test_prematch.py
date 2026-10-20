from app.services.prematch import build_preview


def _m(mid, kickoff, home_id, away_id, hg, ag, comp="Super Lig", finished=True):
    return {
        "id": mid,
        "kickoff": kickoff,
        "finished": finished,
        "cancelled": False,
        "tournament": comp,
        "home_id": home_id,
        "away_id": away_id,
        "home_name": f"T{home_id}",
        "away_name": f"T{away_id}",
        "home_goals": hg,
        "away_goals": ag,
    }


class FakeProvider:
    def __init__(self, home, away, h2h=None):
        self.home = home
        self.away = away
        self.h2h = h2h or []

    def get_team_matches(self, team_id):
        return self.home if team_id == "1" else self.away

    def get_h2h(self, fixture_id):
        return self.h2h


def test_form_and_h2h_counts():
    home = [
        _m("a", "2026-10-10T18:00:00Z", "1", "9", 2, 0),
        _m("b", "2026-10-03T18:00:00Z", "8", "1", 1, 3),
        _m("c", "2026-09-26T18:00:00Z", "1", "7", 1, 1),
        _m("f", "2026-08-01T18:00:00Z", "1", "6", 9, 0, "Club Friendlies"),
        _m("x", "2026-10-20T18:00:00Z", "1", "2", 0, 0, finished=False),
    ]
    away = [
        _m("d", "2026-10-11T18:00:00Z", "5", "2", 1, 2),
        _m("e", "2026-10-04T18:00:00Z", "2", "4", 0, 0),
    ]
    preview = build_preview(FakeProvider(home, away), "1", "2", "Ev", "Dep")
    assert preview["home"]["played"] == 3
    assert preview["home"]["wins"] == 2
    assert preview["home"]["draws"] == 1
    assert preview["home"]["losses"] == 0
    assert preview["home"]["gf"] == 6
    assert preview["home"]["form"] == ["W", "W", "D"]
    assert preview["away"]["played"] == 2
    assert preview["away"]["wins"] == 1
    assert preview["away"]["draws"] == 1


def test_h2h_from_detail_matches():
    home = [_m("a", "2026-10-10T18:00:00Z", "1", "9", 2, 0)]
    away = [_m("b", "2026-10-11T18:00:00Z", "9", "2", 1, 1)]
    h2h = [
        _m("h1", "2024-11-28T20:00:00Z", "2", "1", 1, 2, "Europa League"),
        _m("h2", "2022-02-24T20:00:00Z", "2", "1", 3, 2, "Conference League"),
        _m("h3", "2022-02-17T17:45:00Z", "1", "2", 2, 3, "Conference League"),
    ]
    preview = build_preview(FakeProvider(home, away, h2h), "1", "2", "Ev", "Dep", "777")
    assert preview["h2h"]["played"] == 3
    assert preview["h2h"]["wins"] == 1
    assert preview["h2h"]["losses"] == 2
    assert preview["h2h"]["matches"][0]["date"] == "2024-11-28"


def test_market_probabilities_are_consistent():
    home = [_m(str(i), f"2026-09-{i:02d}T18:00:00Z", "1", "9", 2, 1) for i in range(1, 11)]
    away = [_m(str(i + 20), f"2026-09-{i:02d}T18:00:00Z", "9", "2", 1, 1) for i in range(1, 11)]
    preview = build_preview(FakeProvider(home, away), "1", "2", "Ev", "Dep")
    pred = preview["prediction"]
    assert pred is not None
    markets = pred["markets"]
    assert abs(markets["home_win"] + markets["draw"] + markets["away_win"] - 1) < 0.01
    assert abs(markets["over_1_5"] + (1 - markets["over_1_5"]) - 1) < 0.001
    assert abs(markets["over_2_5"] + markets["under_2_5"] - 1) < 0.001
    assert markets["over_3_5"] <= markets["over_2_5"] <= markets["over_1_5"]
    assert 0 <= markets["btts"] <= 1


def test_no_data_gives_no_prediction():
    preview = build_preview(FakeProvider([], []), "1", "2", "Ev", "Dep")
    assert preview["prediction"] is None
    assert preview["home"]["played"] == 0
