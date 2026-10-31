"""Real-wire adapter: one scapy layer-2 socket per switch port (Linux, needs root)."""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping

from scapy.config import conf
from scapy.error import Scapy_Exception
from scapy.packet import Packet, Raw
from scapy.sendrecv import AsyncSniffer
from scapy.supersocket import SuperSocket

from ..gateways import FrameHandler

logger = logging.getLogger(__name__)


class ScapyFrameIO:
    """Sniffs and sends raw frames on Linux interfaces.

    Each port gets a single ``conf.L2socket`` used both to receive (via an
    AsyncSniffer thread) and to send. On Linux that socket ignores frames the
    host itself transmits, so the switch never re-processes its own output.
    """

    def __init__(self, interfaces: Mapping[str, str]) -> None:
        self._interfaces = dict(interfaces)  # port name -> OS interface
        self._sockets: dict[str, SuperSocket] = {}
        self._sniffers: list[AsyncSniffer] = []

    def start(self, on_frame: FrameHandler) -> None:
        try:
            for port, iface in self._interfaces.items():
                sock = conf.L2socket(iface=iface, promisc=True)
                self._sockets[port] = sock
                sniffer = AsyncSniffer(
                    opened_socket=sock, store=False, prn=self._receiver(port, on_frame)
                )
                sniffer.start()
                self._sniffers.append(sniffer)
                logger.info("port %s bound to interface %s", port, iface)
        except OSError:
            self.stop()
            raise

    def send(self, port: str, frame: bytes) -> None:
        sock = self._sockets.get(port)
        if sock is None:
            return
        try:
            sock.send(Raw(load=frame))
        except OSError as exc:
            logger.warning("send on %s failed: %s", port, exc)

    def stop(self) -> None:
        for sniffer in self._sniffers:
            try:
                sniffer.stop()
            except Scapy_Exception as exc:
                logger.debug("sniffer already stopped: %s", exc)
        for sock in self._sockets.values():
            sock.close()
        self._sniffers.clear()
        self._sockets.clear()

    @staticmethod
    def _receiver(port: str, on_frame: FrameHandler) -> Callable[[Packet], None]:
        def receive(packet: Packet) -> None:
            try:
                on_frame(port, bytes(packet))
            except Exception:  # keep the sniffer thread alive whatever happens
                logger.exception("error processing frame on %s", port)

        return receive
