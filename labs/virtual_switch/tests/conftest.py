from __future__ import annotations

import pytest
from scapy.layers.inet import ICMP, IP
from scapy.layers.l2 import Dot1Q, Ether

from vswitch.adapters.memory_io import MemoryFrameIO
from vswitch.domain import PortConfig, PortMode, StpConfig, SwitchConfig
from vswitch.switch import VirtualSwitch

MAC_A = "00:00:00:00:00:0a"
MAC_B = "00:00:00:00:00:0b"
MAC_C = "00:00:00:00:00:0c"
BROADCAST = "ff:ff:ff:ff:ff:ff"


class FakeClock:
    def __init__(self, start: float = 1000.0) -> None:
        self.value = start

    def now(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


def frame(src: str, dst: str, vlan: int | None = None) -> bytes:
    """An ICMP echo frame, optionally 802.1Q tagged."""
    if vlan is None:
        return bytes(Ether(src=src, dst=dst) / IP() / ICMP())
    return bytes(Ether(src=src, dst=dst) / Dot1Q(vlan=vlan) / IP() / ICMP())


def access(name: str, vlan: int = 1, **kwargs: object) -> PortConfig:
    return PortConfig(name=name, interface=f"if-{name}", access_vlan=vlan, **kwargs)  # type: ignore[arg-type]


def trunk(name: str, **kwargs: object) -> PortConfig:
    return PortConfig(name=name, interface=f"if-{name}", mode=PortMode.TRUNK, **kwargs)  # type: ignore[arg-type]


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def make_switch(clock: FakeClock):
    """Build a started switch (STP off by default) wired to an in-memory wire."""

    def build(ports: list[PortConfig], **config: object) -> tuple[VirtualSwitch, MemoryFrameIO]:
        config.setdefault("stp", StpConfig(enabled=False))
        io = MemoryFrameIO()
        switch = VirtualSwitch(SwitchConfig(name="SW", ports=ports, **config), io, clock)  # type: ignore[arg-type]
        switch.start()
        io.clear()
        return switch, io

    return build
