"""Kota yonetimi ve istek hizi sinirlama.

API-Football ucretsiz plan: 100 istek/gun, 10 istek/dakika.
Kural: kota bittiginde ASLA otomatik olarak ucretli plana gecilmez;
istek reddedilir ve durum kullaniciya bildirilir. Kota koruma payi
(reserve), gunluk kotanin son kismini kritik canli cagrilar icin ayirir.
"""
from __future__ import annotations

import json
import threading
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path


class QuotaExceededError(RuntimeError):
    pass


class QuotaManager:
    def __init__(
        self,
        provider: str,
        daily_limit: int,
        per_minute_limit: int,
        reserve: int = 0,
        state_path: Path | None = None,
    ) -> None:
        self.provider = provider
        self.daily_limit = max(1, daily_limit)
        self.per_minute_limit = max(1, per_minute_limit)
        self.reserve = max(0, min(reserve, self.daily_limit - 1))
        self.state_path = state_path
        self._lock = threading.Lock()
        self._minute_calls: deque[float] = deque()
        self._day, self._daily_used = self._load_state()

    # --- durum ---
    def _today(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def _load_state(self) -> tuple[str, int]:
        if self.state_path and self.state_path.exists():
            try:
                data = json.loads(self.state_path.read_text())
                if data.get("day") == self._today():
                    return data.get("day"), int(data.get("daily_used", 0))
            except (json.JSONDecodeError, ValueError, OSError):
                pass
        return self._today(), 0

    def _save_state(self) -> None:
        if not self.state_path:
            return
        try:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            self.state_path.write_text(
                json.dumps({"day": self._day, "daily_used": self._daily_used})
            )
        except OSError:
            pass

    def _rollover(self) -> None:
        today = self._today()
        if today != self._day:
            self._day = today
            self._daily_used = 0
            self._save_state()

    # --- sorgu ---
    @property
    def daily_used(self) -> int:
        with self._lock:
            self._rollover()
            return self._daily_used

    @property
    def daily_remaining(self) -> int:
        with self._lock:
            self._rollover()
            return max(0, self.daily_limit - self._daily_used)

    def can_call(self, cost: int = 1, consume_reserve: bool = False) -> bool:
        with self._lock:
            self._rollover()
            budget = self.daily_limit if consume_reserve else self.daily_limit - self.reserve
            return self._daily_used + cost <= budget

    def _wait_for_minute_slot(self) -> None:
        now = time.monotonic()
        while self._minute_calls and now - self._minute_calls[0] >= 60:
            self._minute_calls.popleft()
        if len(self._minute_calls) >= self.per_minute_limit:
            sleep_for = 60 - (now - self._minute_calls[0]) + 0.05
            if sleep_for > 0:
                time.sleep(sleep_for)
            return self._wait_for_minute_slot()

    def acquire(self, cost: int = 1, consume_reserve: bool = False) -> None:
        """Kaynak tuketir. Kota yetersizse QuotaExceededError yukseltir."""
        with self._lock:
            self._rollover()
            budget = self.daily_limit if consume_reserve else self.daily_limit - self.reserve
            if self._daily_used + cost > budget:
                raise QuotaExceededError(
                    f"{self.provider}: gunluk kota yetersiz "
                    f"(kullanilan={self._daily_used}, limit={self.daily_limit}, "
                    f"rezerv={0 if consume_reserve else self.reserve}). "
                    "Ucretli plana otomatik gecis yapilmaz."
                )
            self._daily_used += cost
            self._save_state()
            self._wait_for_minute_slot()
            self._minute_calls.append(time.monotonic())

    def release(self, cost: int = 1) -> None:
        """Basarisiz cagri sonrasi kotayi geri verir."""
        with self._lock:
            self._daily_used = max(0, self._daily_used - cost)
            self._save_state()
