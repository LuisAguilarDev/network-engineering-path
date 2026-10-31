"""Simplified IEEE 802.1D Spanning Tree Protocol (pure logic, no I/O).

Implements root bridge election, root/designated/alternate port roles, the
blocking -> listening -> learning -> forwarding state machine, hello timers and
max-age expiry. Topology change notifications are not implemented; MAC aging
takes care of stale entries instead.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, replace

from .domain import StpConfig, StpRole, StpState
from .gateways import Clock

logger = logging.getLogger(__name__)

PORT_NUMBER_BITS = 8
MESSAGE_AGE_INCREMENT = 1.0
_FORWARDING_ROLES = frozenset({StpRole.ROOT, StpRole.DESIGNATED})


@dataclass(frozen=True, order=True)
class BridgeId:
    priority: int
    mac: str

    def __str__(self) -> str:
        return f"{self.priority}.{self.mac}"


@dataclass(frozen=True, order=True)
class PriorityVector:
    """What a bridge advertises; lower is better, compared field by field."""

    root: BridgeId
    root_cost: int
    bridge: BridgeId
    port_id: int


@dataclass(frozen=True)
class Bpdu:
    vector: PriorityVector
    message_age: float
    max_age: float
    hello_time: float
    forward_delay: float


BpduSender = Callable[[str, Bpdu], None]


@dataclass
class StpPort:
    name: str
    port_id: int
    cost: int
    portfast: bool
    enabled: bool = False
    role: StpRole = StpRole.DISABLED
    state: StpState = StpState.DISABLED
    state_since: float = 0.0
    received: Bpdu | None = None
    received_at: float = 0.0


def make_port_id(priority: int, number: int) -> int:
    return (priority << PORT_NUMBER_BITS) | number


class SpanningTree:
    def __init__(
        self, bridge_id: BridgeId, config: StpConfig, clock: Clock, send_bpdu: BpduSender
    ) -> None:
        self.bridge_id = bridge_id
        self.config = config
        self._clock = clock
        self._send = send_bpdu
        self._ports: dict[str, StpPort] = {}
        self.root_id = bridge_id
        self.root_cost = 0
        self.root_port: str | None = None
        self._last_hello = float("-inf")

    @property
    def is_root(self) -> bool:
        return self.root_port is None

    def add_port(
        self, name: str, number: int, cost: int, priority: int, portfast: bool = False
    ) -> None:
        self._ports[name] = StpPort(name, make_port_id(priority, number), cost, portfast)

    def set_port_enabled(self, name: str, enabled: bool) -> None:
        port = self._ports[name]
        if port.enabled == enabled:
            return
        port.enabled = enabled
        port.received = None
        if not enabled:
            self._set_role_state(port, StpRole.DISABLED, StpState.DISABLED)
        self._recompute()

    def receive(self, name: str, bpdu: Bpdu) -> None:
        port = self._ports.get(name)
        if port is None or not port.enabled:
            return
        port.received = bpdu
        port.received_at = self._clock.now()
        self._recompute()

    def tick(self) -> None:
        now = self._clock.now()
        if self._expire_stale_info(now):
            self._recompute()
        self._advance_timers(now)
        if now - self._last_hello >= self.config.hello_time:
            self._last_hello = now
            for port in self._enabled_ports():
                if port.role is StpRole.DESIGNATED:
                    self._send_config_bpdu(port)

    def state(self, name: str) -> StpState:
        return self._ports[name].state

    def ports(self) -> list[StpPort]:
        return [replace(port) for port in self._ports.values()]

    def _enabled_ports(self) -> list[StpPort]:
        return [port for port in self._ports.values() if port.enabled]

    def _expire_stale_info(self, now: float) -> bool:
        expired = False
        for port in self._enabled_ports():
            info = port.received
            if info is not None and info.message_age + (now - port.received_at) >= info.max_age:
                logger.info("STP: BPDU info on %s expired", port.name)
                port.received = None
                expired = True
        return expired

    def _recompute(self) -> None:
        best: tuple[tuple[BridgeId, int, BridgeId, int, int], StpPort] | None = None
        for port in self._enabled_ports():
            if port.received is None:
                continue
            rx = port.received.vector
            candidate = (rx.root, rx.root_cost + port.cost, rx.bridge, rx.port_id, port.port_id)
            if best is None or candidate < best[0]:
                best = (candidate, port)

        new_root: tuple[BridgeId, int, str | None]
        if best is not None and best[0][0] < self.bridge_id:
            (root, cost, *_), root_port = best
            new_root = (root, cost, root_port.name)
        else:
            new_root = (self.bridge_id, 0, None)
        if new_root != (self.root_id, self.root_cost, self.root_port):
            logger.info("STP: root %s cost %d via %s", new_root[0], new_root[1], new_root[2])
        self.root_id, self.root_cost, self.root_port = new_root

        for port in self._enabled_ports():
            self._assign_role(port, self._role_for(port))

    def _role_for(self, port: StpPort) -> StpRole:
        if port.name == self.root_port:
            return StpRole.ROOT
        if port.received is None or self._designated_vector(port) < port.received.vector:
            return StpRole.DESIGNATED
        return StpRole.ALTERNATE

    def _designated_vector(self, port: StpPort) -> PriorityVector:
        return PriorityVector(self.root_id, self.root_cost, self.bridge_id, port.port_id)

    def _assign_role(self, port: StpPort, role: StpRole) -> None:
        if port.role == role:
            return
        logger.info("STP: %s role %s -> %s", port.name, port.role, role)
        if role is StpRole.ALTERNATE:
            state = StpState.BLOCKING
        elif port.role in _FORWARDING_ROLES:
            state = port.state
        else:
            state = StpState.FORWARDING if port.portfast else StpState.LISTENING
        self._set_role_state(port, role, state)
        if role is StpRole.DESIGNATED:
            self._send_config_bpdu(port)

    def _set_role_state(self, port: StpPort, role: StpRole, state: StpState) -> None:
        port.role = role
        if port.state != state:
            port.state = state
            port.state_since = self._clock.now()

    def _advance_timers(self, now: float) -> None:
        for port in self._enabled_ports():
            if now - port.state_since < self.config.forward_delay:
                continue
            if port.state is StpState.LISTENING:
                self._set_role_state(port, port.role, StpState.LEARNING)
            elif port.state is StpState.LEARNING:
                self._set_role_state(port, port.role, StpState.FORWARDING)
                logger.info("STP: %s is forwarding", port.name)

    def _send_config_bpdu(self, port: StpPort) -> None:
        self._send(
            port.name,
            Bpdu(
                vector=self._designated_vector(port),
                message_age=self._message_age(),
                max_age=self.config.max_age,
                hello_time=self.config.hello_time,
                forward_delay=self.config.forward_delay,
            ),
        )

    def _message_age(self) -> float:
        if self.root_port is None:
            return 0.0
        root_info = self._ports[self.root_port].received
        return root_info.message_age + MESSAGE_AGE_INCREMENT if root_info else 0.0
