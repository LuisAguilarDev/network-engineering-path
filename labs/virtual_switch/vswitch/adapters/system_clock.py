"""Wall clock based on a monotonic timer (immune to system time changes)."""

from __future__ import annotations

import time


class SystemClock:
    def now(self) -> float:
        return time.monotonic()
