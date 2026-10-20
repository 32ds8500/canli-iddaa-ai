"""Kisa omurlu, islem ici yanit onbellegi.

Pahali liste yanitlari (canli/bugun) ayni sure icinde tekrar tekrar
hesaplanmasin diye kullanilir. Onbellek tek surecte tutulur; sure dolunca
yeniden uretilir.
"""
from __future__ import annotations

import threading
import time
from typing import Any, Callable

_lock = threading.Lock()
_store: dict[str, tuple[float, Any]] = {}


def get(key: str) -> tuple[Any, float] | None:
    with _lock:
        hit = _store.get(key)
    if hit is None:
        return None
    value, created = hit
    return value, time.monotonic() - created


def put(key: str, value: Any) -> None:
    with _lock:
        _store[key] = (value, time.monotonic())


def cached(key: str, ttl: float, builder: Callable[[], Any]) -> Any:
    hit = get(key)
    if hit is not None and hit[1] < ttl:
        return hit[0]
    value = builder()
    put(key, value)
    return value


def invalidate(prefix: str = "") -> None:
    with _lock:
        for key in list(_store):
            if key.startswith(prefix):
                _store.pop(key, None)
