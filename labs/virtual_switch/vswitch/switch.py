"""The forwarding engine: VLANs, MAC learning, STP, port security, storm control and SPAN.

Frame pipeline for every received frame:

    port up? -> parse -> BPDU? -> SPAN rx -> VLAN ingress -> STP learn state
    -> port security -> MAC learning -> STP forward state -> storm control
    -> forward / filter / flood -> VLAN egress (tag/untag) -> SPAN tx
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field

from .bpdu_codec import decode_bpdu, encode_bpdu
from .domain import (
    STP_MULTICAST_MAC,
    PortConfig,
    PortCounters,
    PortMode,
    SpanDirection,
    SpanSession,
    StpConfig,
    StpState,
    SwitchConfig,
)
from .frames import parse_frame
from .gateways import Clock, FrameIO
from .mac import is_multicast, normalize_mac
from .mac_table import MacAddressTable
from .port_security import PortSecurity, SecurityVerdict
from .storm_control import StormControl
from .stp import Bpdu, BridgeId, SpanningTree
from .vlan import VlanDatabase, egress_frame, ingress_vlan, validate_vlan_id

logger = logging.getLogger(__name__)

ERR_PSECURE = "psecure-violation"
ERR_BPDU_GUARD = "bpduguard"
STATUS_CONNECTED = "connected"
STATUS_DISABLED = "disabled"
STATUS_ERR_DISABLED = "err-disabled"
_LEARNING_STATES = frozenset({StpState.LEARNING, StpState.FORWARDING})


@dataclass
class SwitchPort:
    config: PortConfig
    number: int
    counters: PortCounters = field(default_factory=PortCounters)
    err_disabled_reason: str | None = None

    @property
    def name(self) -> str:
        return self.config.name

    @property
    def is_up(self) -> bool:
        return self.config.enabled and self.err_disabled_reason is None

    @property
    def status(self) -> str:
        if self.err_disabled_reason is not None:
            return STATUS_ERR_DISABLED
        return STATUS_CONNECTED if self.config.enabled else STATUS_DISABLED


class VirtualSwitch:
    def __init__(self, config: SwitchConfig, io: FrameIO, clock: Clock) -> None:
        self.name = config.name
        self.bridge_mac = config.bridge_mac
        self._io = io
        self._clock = clock
        self._lock = threading.RLock()
        self.vlans = VlanDatabase(config.vlans)
        self.mac_table = MacAddressTable(clock, config.mac_aging_time)
        self.port_security = PortSecurity()
        self.storm_control = StormControl(clock)
        self._ports = {p.name: SwitchPort(p, n) for n, p in enumerate(config.ports, start=1)}
        self.span_sessions: list[SpanSession] = list(config.span_sessions)
        self.stp = self._build_stp(config.stp)
        for static in config.static_macs:
            self.mac_table.add_static(static.mac, static.vlan, static.port)

    def _build_stp(self, config: StpConfig) -> SpanningTree | None:
        if not config.enabled:
            return None
        stp = SpanningTree(
            BridgeId(config.priority, self.bridge_mac), config, self._clock, self._send_bpdu
        )
        for port in self._ports.values():
            stp.add_port(
                port.name,
                port.number,
                port.config.stp_cost,
                port.config.stp_priority,
                port.config.portfast,
            )
        return stp

    # ----------------------------------------------------------------- lifecycle

    def start(self) -> None:
        self._io.start(self.handle_frame)
        with self._lock:
            if self.stp is not None:
                for port in self._ports.values():
                    if port.is_up:
                        self.stp.set_port_enabled(port.name, True)

    def stop(self) -> None:
        self._io.stop()

    def tick(self) -> None:
        """Periodic housekeeping: MAC aging and STP timers. Call about once per second."""
        with self._lock:
            self.mac_table.age_out()
            if self.stp is not None:
                self.stp.tick()

    @contextmanager
    def locked(self) -> Iterator[None]:
        """Hold the engine lock so a reader sees a consistent snapshot."""
        with self._lock:
            yield

    # ------------------------------------------------------------- data plane

    def handle_frame(self, port_name: str, raw: bytes) -> None:
        with self._lock:
            port = self._ports.get(port_name)
            if port is not None and port.is_up:
                self._process(port, raw)

    def _process(self, port: SwitchPort, raw: bytes) -> None:
        try:
            frame = parse_frame(raw)
        except ValueError:
            port.counters.dropped += 1
            return
        port.counters.record_rx(len(raw), frame.dst)

        if frame.dst == STP_MULTICAST_MAC and self._consume_bpdu(port, raw):
            return
        if self._is_span_destination(port.name):
            port.counters.dropped += 1
            return
        self._mirror(port.name, raw, SpanDirection.RX)

        vlan = ingress_vlan(port.config, frame.vlan_tag)
        if vlan is None or not self.vlans.exists(vlan) or is_multicast(frame.src):
            port.counters.dropped += 1
            return
        if not self._can_learn(port) or not self._admit_source(port, frame.src, vlan):
            port.counters.dropped += 1
            return
        self.mac_table.learn(frame.src, vlan, port.name)
        if not self._can_forward(port):
            return
        if is_multicast(frame.dst) and not self.storm_control.allow(
            port.name, port.config.storm_control_pps
        ):
            port.counters.dropped += 1
            return

        for egress in self._egress_ports(port, frame.dst, vlan):
            self._transmit(egress, vlan, frame.untagged)

    def _consume_bpdu(self, port: SwitchPort, raw: bytes) -> bool:
        """Handle a frame sent to the STP group address. False means "forward it as data"."""
        if port.config.bpdu_guard:
            self._err_disable(port, ERR_BPDU_GUARD)
            return True
        if self.stp is None:
            return False
        bpdu = decode_bpdu(raw)
        if bpdu is not None:
            self.stp.receive(port.name, bpdu)
        return True

    def _admit_source(self, port: SwitchPort, mac: str, vlan: int) -> bool:
        verdict = self.port_security.check(port.config, mac, vlan)
        if verdict is SecurityVerdict.SHUTDOWN:
            self._err_disable(port, ERR_PSECURE)
        return verdict is SecurityVerdict.ALLOW

    def _egress_ports(self, ingress: SwitchPort, dst: str, vlan: int) -> list[SwitchPort]:
        if not is_multicast(dst):
            known = self.mac_table.lookup(dst, vlan)
            if known is not None:
                target = self._ports.get(known)
                if known == ingress.name or target is None or not self._can_forward(target):
                    return []  # filtered: destination is on the ingress segment
                return [target]
        return [
            port
            for port in self._ports.values()
            if port is not ingress
            and self._can_forward(port)
            and port.config.carries_vlan(vlan)
            and not self._is_span_destination(port.name)
        ]

    def _transmit(self, port: SwitchPort, vlan: int, untagged: bytes) -> None:
        out = egress_frame(port.config, vlan, untagged)
        if out is None:
            return
        self._send(port, out)
        self._mirror(port.name, out, SpanDirection.TX)

    def _send(self, port: SwitchPort, raw: bytes) -> None:
        self._io.send(port.name, raw)
        port.counters.record_tx(len(raw))

    def _send_bpdu(self, port_name: str, bpdu: Bpdu) -> None:
        port = self._ports[port_name]
        if port.is_up:
            self._send(port, encode_bpdu(bpdu, self.bridge_mac))

    def _mirror(self, source: str, raw: bytes, direction: SpanDirection) -> None:
        for session in self.span_sessions:
            if source not in session.sources:
                continue
            if session.direction not in (direction, SpanDirection.BOTH):
                continue
            destination = self._ports.get(session.destination)
            if destination is not None and destination.is_up:
                self._send(destination, raw)

    def _is_span_destination(self, port_name: str) -> bool:
        return any(session.destination == port_name for session in self.span_sessions)

    def _can_learn(self, port: SwitchPort) -> bool:
        return port.is_up and (self.stp is None or self.stp.state(port.name) in _LEARNING_STATES)

    def _can_forward(self, port: SwitchPort) -> bool:
        return port.is_up and (self.stp is None or self.stp.state(port.name) is StpState.FORWARDING)

    # ---------------------------------------------------------- control plane

    def ports(self) -> list[SwitchPort]:
        return list(self._ports.values())

    def port(self, name: str) -> SwitchPort:
        """Find a port by name, case-insensitively (``gi0/1`` matches ``Gi0/1``)."""
        for port in self._ports.values():
            if port.name.lower() == name.lower():
                return port
        raise ValueError(f"unknown interface {name!r}")

    def shutdown(self, name: str) -> None:
        with self._lock:
            port = self.port(name)
            port.config.enabled = False
            self._port_down(port)

    def no_shutdown(self, name: str) -> None:
        """Bring a port up, recovering it from err-disabled if needed."""
        with self._lock:
            port = self.port(name)
            port.config.enabled = True
            port.err_disabled_reason = None
            self.port_security.clear(port.name)
            if self.stp is not None:
                self.stp.set_port_enabled(port.name, True)

    def _err_disable(self, port: SwitchPort, reason: str) -> None:
        logger.warning("%s err-disabled: %s", port.name, reason)
        port.err_disabled_reason = reason
        self._port_down(port)

    def _port_down(self, port: SwitchPort) -> None:
        self.mac_table.flush(port=port.name)
        if self.stp is not None:
            self.stp.set_port_enabled(port.name, False)

    def set_access_vlan(self, name: str, vlan: int) -> None:
        with self._lock:
            port = self.port(name)
            self.vlans.add(validate_vlan_id(vlan))  # IOS auto-creates the VLAN
            port.config.access_vlan = vlan
            self.mac_table.flush(port=port.name)

    def set_mode(self, name: str, mode: PortMode) -> None:
        with self._lock:
            port = self.port(name)
            port.config.mode = mode
            self.mac_table.flush(port=port.name)

    def set_allowed_vlans(self, name: str, vlans: frozenset[int] | None) -> None:
        with self._lock:
            self.port(name).config.allowed_vlans = vlans

    def set_native_vlan(self, name: str, vlan: int) -> None:
        with self._lock:
            self.port(name).config.native_vlan = validate_vlan_id(vlan)

    def add_vlan(self, vlan: int, vlan_name: str | None = None) -> None:
        with self._lock:
            self.vlans.add(vlan, vlan_name)

    def remove_vlan(self, vlan: int) -> None:
        with self._lock:
            self.vlans.remove(vlan)
            self.mac_table.flush(vlan=vlan, include_static=True)

    def add_static_mac(self, mac: str, vlan: int, port_name: str) -> None:
        with self._lock:
            if not self.vlans.exists(vlan):
                raise ValueError(f"VLAN {vlan} does not exist")
            self.mac_table.add_static(normalize_mac(mac), vlan, self.port(port_name).name)

    def remove_static_mac(self, mac: str, vlan: int) -> None:
        with self._lock:
            if not self.mac_table.remove_static(normalize_mac(mac), vlan):
                raise ValueError(f"no static entry for {mac} in VLAN {vlan}")

    def clear_mac_table(self) -> int:
        with self._lock:
            return self.mac_table.flush()

    def clear_counters(self) -> None:
        with self._lock:
            for port in self._ports.values():
                port.counters = PortCounters()
