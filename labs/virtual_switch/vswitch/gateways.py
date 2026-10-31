"""Abstractions over the outside world: the wire and the clock.

The forwarding engine only depends on these protocols, so it can be driven by
real interfaces (scapy) in the lab and by in-memory fakes in the tests.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

FrameHandler = Callable[[str, bytes], None]
"""Called with ``(port_name, raw_frame)`` for every frame received on a port."""


class FrameIO(Protocol):
    def start(self, on_frame: FrameHandler) -> None: ...

    def send(self, port: str, frame: bytes) -> None: ...

    def stop(self) -> None: ...


class Clock(Protocol):
    def now(self) -> float: ...
