"""In-memory wire used by tests and demos: inject frames, inspect what was sent."""

from __future__ import annotations

from ..gateways import FrameHandler


class MemoryFrameIO:
    def __init__(self) -> None:
        self.sent: list[tuple[str, bytes]] = []
        self._handler: FrameHandler | None = None

    def start(self, on_frame: FrameHandler) -> None:
        self._handler = on_frame

    def send(self, port: str, frame: bytes) -> None:
        self.sent.append((port, frame))

    def stop(self) -> None:
        self._handler = None

    def inject(self, port: str, frame: bytes) -> None:
        if self._handler is None:
            raise RuntimeError("MemoryFrameIO.inject called before start()")
        self._handler(port, frame)

    def sent_on(self, port: str) -> list[bytes]:
        return [frame for name, frame in self.sent if name == port]

    def clear(self) -> None:
        self.sent.clear()
