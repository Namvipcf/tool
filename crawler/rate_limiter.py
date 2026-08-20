"""Rate limiter: gian cach request + exponential backoff."""

from __future__ import annotations

import random
import threading
import time

from utils.logger import get_logger

log = get_logger("rate_limiter")


class RateLimiter:
    """Bao dam khoang cach toi thieu giua 2 request va tinh thoi gian backoff.

    `jitter` tranh viec cac request deu tap nhau chinh xac moi `delay` giay.
    """

    def __init__(self, delay: float = 2.0, jitter: float = 0.3, max_backoff: float = 120.0) -> None:
        self.delay = max(0.0, float(delay))
        self.jitter = max(0.0, float(jitter))
        self.max_backoff = max_backoff
        self._last = 0.0
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    def set_delay(self, delay: float) -> None:
        with self._lock:
            self.delay = max(0.0, float(delay))

    def wait(self) -> float:
        """Chan lai cho du delay; tra ve so giay da ngu."""
        with self._lock:
            now = time.monotonic()
            target = self._last + self.delay * (1.0 + random.uniform(-self.jitter, self.jitter))
            sleep_for = max(0.0, target - now)
            self._last = now + sleep_for
        if sleep_for:
            time.sleep(sleep_for)
        return sleep_for

    def backoff(self, attempt: int, retry_after: float | None = None) -> float:
        """Tra ve so giay cho truoc lan retry thu `attempt` (bat dau tu 1)."""
        if retry_after and retry_after > 0:
            return min(float(retry_after), self.max_backoff)
        base = max(self.delay, 1.0)
        return min(base * (2 ** max(0, attempt - 1)), self.max_backoff)
