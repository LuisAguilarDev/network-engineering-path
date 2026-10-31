"""Domain models for the virtual switch: pure data shared by every layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from .mac import is_multicast

BROADCAST_MAC = "ff:ff:ff:ff:ff:ff"
STP_MULTICAST_MAC = "01:80:c2:00:00:00"
DEFAULT_BRIDGE_MAC = "02:00:00:00:00:01"
DEFAULT_VLAN = 1
MIN_VLAN = 1
MAX_VLAN = 4094
DEFAULT_MAC_AGING_SECONDS = 300.0
DEFAULT_STP_PORT_COST = 19  # IEEE 802.1D short cost for a 100 Mb/s link
DEFAULT_STP_PORT_PRIORITY = 128
DEFAULT_STP_BRIDGE_PRIORITY = 32768


class PortMode(StrEnum):
    ACCESS = "access"
    TRUNK = "trunk"


class ViolationMode(StrEnum):
    PROTECT = "protect"  # drop offending frames silently
    RESTRICT = "restrict"  # drop and count the violation
    SHUTDOWN = "shutdown"  # err-disable the port


class StpState(StrEnum):
    DISABLED = "disabled"
    BLOCKING = "blocking"
    LISTENING = "listening"
    LEARNING = "learning"
    FORWARDING = "forwarding"


class StpRole(StrEnum):
    ROOT = "root"
    DESIGNATED = "designated"
    ALTERNATE = "alternate"
    DISABLED = "disabled"


class SpanDirection(StrEnum):
    RX = "rx"
    TX = "tx"
    BOTH = "both"


@dataclass(frozen=True)
class PortSecurityConfig:
    max_macs: int = 1
    violation: ViolationMode = ViolationMode.SHUTDOWN


@dataclass
class PortConfig:
    name: str
    interface: str
    mode: PortMode = PortMode.ACCESS
    access_vlan: int = DEFAULT_VLAN
    native_vlan: int = DEFAULT_VLAN
    allowed_vlans: frozenset[int] | None = None  # None means "all VLANs"
    enabled: bool = True
    description: str = ""
    port_security: PortSecurityConfig | None = None
    storm_control_pps: int | None = None
    stp_cost: int = DEFAULT_STP_PORT_COST
    stp_priority: int = DEFAULT_STP_PORT_PRIORITY
    portfast: bool = False
    bpdu_guard: bool = False

    def carries_vlan(self, vlan: int) -> bool:
        if self.mode is PortMode.ACCESS:
            return vlan == self.access_vlan
        return self.allowed_vlans is None or vlan in self.allowed_vlans


@dataclass
class PortCounters:
    rx_frames: int = 0
    rx_bytes: int = 0
    rx_broadcast: int = 0
    rx_multicast: int = 0
    tx_frames: int = 0
    tx_bytes: int = 0
    dropped: int = 0

    def record_rx(self, size: int, dst: str) -> None:
        self.rx_frames += 1
        self.rx_bytes += size
        if dst == BROADCAST_MAC:
            self.rx_broadcast += 1
        elif is_multicast(dst):
            self.rx_multicast += 1

    def record_tx(self, size: int) -> None:
        self.tx_frames += 1
        self.tx_bytes += size


@dataclass(frozen=True)
class MacEntry:
    mac: str
    vlan: int
    port: str
    static: bool
    last_seen: float


@dataclass(frozen=True)
class StaticMac:
    mac: str
    vlan: int
    port: str


@dataclass(frozen=True)
class SpanSession:
    session_id: int
    sources: frozenset[str]
    destination: str
    direction: SpanDirection = SpanDirection.BOTH


@dataclass(frozen=True)
class StpConfig:
    enabled: bool = True
    priority: int = DEFAULT_STP_BRIDGE_PRIORITY
    hello_time: float = 2.0
    forward_delay: float = 15.0
    max_age: float = 20.0


@dataclass
class SwitchConfig:
    name: str
    ports: list[PortConfig]
    bridge_mac: str = DEFAULT_BRIDGE_MAC
    vlans: dict[int, str] = field(default_factory=dict)
    stp: StpConfig = field(default_factory=StpConfig)
    mac_aging_time: float = DEFAULT_MAC_AGING_SECONDS
    static_macs: list[StaticMac] = field(default_factory=list)
    span_sessions: list[SpanSession] = field(default_factory=list)
