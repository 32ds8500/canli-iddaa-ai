from datetime import datetime, timezone

from app.timeutil import day_bounds_utc, in_day


def test_day_bounds_are_utc_plus_three():
    start, end = day_bounds_utc("2026-10-20")
    assert start == datetime(2026, 10, 19, 21, 0, tzinfo=timezone.utc)
    assert end == datetime(2026, 10, 20, 21, 0, tzinfo=timezone.utc)


def test_in_day_includes_boundaries_correctly():
    assert in_day(datetime(2026, 10, 19, 21, 0), "2026-10-20")
    assert in_day(datetime(2026, 10, 20, 20, 59), "2026-10-20")
    assert not in_day(datetime(2026, 10, 20, 21, 0), "2026-10-20")
    assert not in_day(datetime(2026, 10, 19, 20, 59), "2026-10-20")


def test_in_day_handles_timezone_aware():
    from datetime import timedelta

    tz3 = timezone(timedelta(hours=3))
    assert in_day(datetime(2026, 10, 20, 0, 30, tzinfo=tz3), "2026-10-20")
    assert not in_day(None, "2026-10-20")
