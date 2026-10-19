import pytest

from app.providers.quota import QuotaExceededError, QuotaManager


def _qm(tmp_path, daily=10, per_min=1000, reserve=2):
    return QuotaManager("test", daily, per_min, reserve, state_path=tmp_path / "q.json")


def test_daily_limit_and_reserve(tmp_path):
    qm = _qm(tmp_path, daily=5, reserve=1)
    # rezerv disi butce = 4
    for _ in range(4):
        assert qm.can_call()
        qm.acquire()
    assert qm.daily_used == 4
    assert qm.can_call() is False
    with pytest.raises(QuotaExceededError):
        qm.acquire()
    # rezerv dahil edilirse 1 hak kalir
    assert qm.can_call(consume_reserve=True) is True
    qm.acquire(consume_reserve=True)
    assert qm.daily_used == 5


def test_release_restores_budget(tmp_path):
    qm = _qm(tmp_path, daily=3, reserve=0)
    qm.acquire()
    assert qm.daily_used == 1
    qm.release()
    assert qm.daily_used == 0


def test_state_persistence(tmp_path):
    qm1 = _qm(tmp_path, daily=5, reserve=0)
    qm1.acquire()
    qm1.acquire()
    qm2 = _qm(tmp_path, daily=5, reserve=0)
    assert qm2.daily_used == 2


def test_remaining(tmp_path):
    qm = _qm(tmp_path, daily=7, reserve=0)
    assert qm.daily_remaining == 7
    qm.acquire()
    assert qm.daily_remaining == 6
