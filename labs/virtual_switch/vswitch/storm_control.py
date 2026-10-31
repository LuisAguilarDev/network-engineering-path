"""Storm control: cap broadcast/multicast frames per second on a port."""

from __future__ import annotations

from collections import defaultdict

from .gateways import Clock

WINDOW_SECONDS = 1.0


class StormControl:
    def __init__(self, clock: Clock) -> None:
        self._clock = clock
        self._windows: dict[str, tuple[int, int]] = {}
        self._suppressed: defaultdict[str, int] = defaultdict(int)

    def allow(self, port: str, limit_pps: int | None) -> bool:
        if limit_pps is None:
            return True
        window = int(self._clock.now() // WINDOW_SECONDS)
        start, count = self._windows.get(port, (window, 0))
        count = count + 1 if start == window else 1
        self._windows[port] = (window, count)
        if count > limit_pps:
            self._suppressed[port] += 1
            return False
        return True

    def suppressed(self, port: str) -> int:
        return self._suppressed.get(port, 0)
