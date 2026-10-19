import pytest

from app.eval.chronological import assert_no_leakage, split_chronological


def test_split_keeps_order_and_sizes():
    items = list(range(100))
    split = split_chronological(items, 0.6, 0.2)
    assert len(split.train) == 60
    assert len(split.validation) == 20
    assert len(split.test) == 20
    assert split.train == list(range(60))
    assert split.test == list(range(80, 100))


def test_split_small_dataset():
    split = split_chronological([1], 0.6, 0.2)
    assert split.train == [1]
    assert split.validation == []
    assert split.test == []


def test_no_leakage_detection():
    assert_no_leakage([1, 2, 3], [4, 5], [6, 7])
    with pytest.raises(AssertionError):
        assert_no_leakage([1, 2, 10], [4, 5], [6, 7])


def test_invalid_ratios():
    with pytest.raises(ValueError):
        split_chronological([1, 2, 3], 0.9, 0.2)
