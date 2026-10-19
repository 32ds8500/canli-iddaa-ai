"""Zorunlu sinir durumu testleri (spesifikasyon madde 11)."""
from datetime import datetime, timezone

import httpx
import pytest

from app.config import Settings
from app.engines.baselines import prior_baseline
from app.engines.corner_model import CornerModel
from app.engines.goal_model import GoalModel
from app.eval.report import minute_bucket
from app.ingest.live import LIVE_SHORT_STATUSES
from app.ingest.normalizer import FINISHED_STATUSES
from app.providers.api_football import ApiFootballProvider
from app.providers.base import ProviderError
from tests.helpers import make_features


def _settings(**kw):
    base = dict(
        api_football_key="test-key",
        daily_quota=100,
        per_minute_quota=1000,
        quota_reserve=0,
        http_max_retries=2,
    )
    base.update(kw)
    return Settings(**base)


def _provider(handler):
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return ApiFootballProvider(_settings(), client=client)


def test_quota_exceeded_does_not_escalate():
    def handler(request):
        return httpx.Response(200, json={"response": [], "errors": []})

    provider = _provider(handler)
    provider._quota.daily_limit = 1
    provider._quota.reserve = 0
    # get_status ttl=0 -> onbellek kullanmaz, her seferinde kota tuketir
    provider.get_status()
    with pytest.raises(ProviderError) as exc:
        provider.get_status()
    assert "kota" in str(exc.value).lower()


def test_api_rate_limit_429_retries_then_raises():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(429, json={"errors": {"rateLimit": "too many"}})

    provider = _provider(handler)
    with pytest.raises(ProviderError):
        provider.get_live_fixtures()
    assert calls["n"] >= 2  # yeniden deneme yapildi


def test_api_outage_connect_error():
    def handler(request):
        raise httpx.ConnectError("baglanti yok")

    provider = _provider(handler)
    with pytest.raises(ProviderError) as exc:
        provider.get_live_fixtures()
    assert exc.value.retryable is True


def test_auth_error_raises():
    def handler(request):
        return httpx.Response(401, json={"errors": {"token": "invalid"}})

    provider = _provider(handler)
    with pytest.raises(ProviderError) as exc:
        provider.get_live_fixtures()
    assert exc.value.status_code == 401


def test_not_configured():
    provider = ApiFootballProvider(_settings(api_football_key=""))
    with pytest.raises(ProviderError):
        provider.get_live_fixtures()
    assert provider.is_configured() is False


@pytest.mark.parametrize(
    "sh,score",
    [("NS", (0, 0)), ("1H", (0, 0)), ("1H", (1, 0)), ("2H", (0, 1)), ("2H", (4, 3)),
     ("HT", (1, 1)), ("ET", (2, 2)), ("FT", (3, 1)), ("PST", (0, 0)), ("CANC", (0, 0))],
)
def test_scores_and_statuses_produce_valid_probabilities(sh, score):
    feats = make_features(minute=45, score_home=score[0], score_away=score[1])
    g = GoalModel().run(feats, prior_baseline("203"))
    c = CornerModel().run(feats, prior_baseline("203"))
    assert g.sufficient and c.sufficient
    for p in g.predictions + c.predictions:
        assert 0.0 <= p.probability <= 1.0


def test_status_sets_are_disjoint():
    assert LIVE_SHORT_STATUSES.isdisjoint(FINISHED_STATUSES)
    assert "FT" in FINISHED_STATUSES
    assert "PST" not in LIVE_SHORT_STATUSES
    assert "CANC" not in LIVE_SHORT_STATUSES
    assert "NS" not in LIVE_SHORT_STATUSES


@pytest.mark.parametrize(
    "minute,expected",
    [(0, "0-15"), (14, "0-15"), (15, "15-30"), (44, "30-45"), (45, "45-60"),
     (74, "60-75"), (75, "75-90+"), (95, "75-90+"), (None, "bilinmiyor")],
)
def test_minute_buckets(minute, expected):
    assert minute_bucket(minute) == expected


def test_extra_time_minute_clamped_remaining():
    feats = make_features(minute=95, score_home=1, score_away=1)
    assert feats.remaining_minutes == 0  # remaining = max(0, 90-95)
    g = GoalModel().run(feats, prior_baseline("203"))
    # kalan sure 0 -> kalan mac golu olasiligi 0
    probs = {p.market: p.probability for p in g.predictions}
    assert probs["goal_rest_at_least_one"] == 0.0


def test_no_shots_low_probabilities():
    feats = make_features(minute=70, score_home=0, score_away=0, shots_home=0, shots_away=0,
                          w10_home_shots_on=0, w10_away_shots_on=0)
    g = GoalModel().run(feats, prior_baseline("203"))
    probs = {p.market: p.probability for p in g.predictions}
    # sut yok, kalan az; 5 dk gol olasiligi dusuk olmali
    assert probs["goal_next_5_min"] < 0.2


def test_consecutive_corners_do_not_imply_certainty():
    feats = make_features(minute=20, w10_home_corners=5, w10_away_corners=3)
    c = CornerModel().run(feats, prior_baseline("203"))
    probs = {p.market: p.probability for p in c.predictions}
    # kumelenme olsa da 5 dk korner olasiligi 1 olmamali
    assert probs["corner_next_5_min"] < 1.0
