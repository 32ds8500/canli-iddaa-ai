"""Uygulama saat dilimi yardimcilari.

Turkiye kalici UTC+3'tur; gun sinirlari bu ofsete gore hesaplanir.
SQLite'tan gelen naive zamanlar UTC kabul edilir.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

from app.config import get_settings


def app_timezone() -> timezone:
    return timezone(timedelta(hours=get_settings().app_utc_offset_hours))


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def parse_local_date(value: str) -> date:
    return date.fromisoformat(value)


def day_bounds_utc(value: str) -> tuple[datetime, datetime]:
    """Yerel takvim gununu UTC [baslangic, bitis) araligina cevirir."""
    local_day = parse_local_date(value)
    start = datetime.combine(local_day, time.min, tzinfo=app_timezone())
    end = start + timedelta(days=1)
    return start.astimezone(timezone.utc), end.astimezone(timezone.utc)


def local_today() -> date:
    return datetime.now(app_timezone()).date()


def in_day(value: datetime | None, day: str) -> bool:
    if value is None:
        return False
    start, end = day_bounds_utc(day)
    return start <= as_utc(value) < end
