"""Port security: limit how many source MACs a port accepts."""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from enum import Enum, auto

from .domain import PortConfig, ViolationMode

logger = logging.getLogger(__name__)


class SecurityVerdict(Enum):
    ALLOW = auto()
    DROP = auto()
    SHUTDOWN = auto()


@dataclass(frozen=True)
class PortSecurityStatus:
    secure_macs: tuple[tuple[str, int], ...]
    violations: int
    last_violator: str | None


class PortSecurity:
    def __init__(self) -> None:
        self._secure: defaultdict[str, set[tuple[str, int]]] = defaultdict(set)
        self._violations: defaultdict[str, int] = defaultdict(int)
        self._last_violator: dict[str, str] = {}

    def check(self, port: PortConfig, mac: str, vlan: int) -> SecurityVerdict:
        settings = port.port_security
        if settings is None:
            return SecurityVerdict.ALLOW
        secure = self._secure[port.name]
        if (mac, vlan) in secure:
            return SecurityVerdict.ALLOW
        if len(secure) < settings.max_macs:
            secure.add((mac, vlan))
            return SecurityVerdict.ALLOW
        return self._violation(port.name, settings.violation, mac)

    def _violation(self, port: str, mode: ViolationMode, mac: str) -> SecurityVerdict:
        if mode is ViolationMode.PROTECT:
            return SecurityVerdict.DROP
        self._violations[port] += 1
        self._last_violator[port] = mac
        logger.warning("port-security violation on %s from %s (%s)", port, mac, mode)
        if mode is ViolationMode.RESTRICT:
            return SecurityVerdict.DROP
        return SecurityVerdict.SHUTDOWN

    def clear(self, port: str) -> None:
        """Forget secure MACs, e.g. when an err-disabled port is recovered."""
        self._secure.pop(port, None)

    def status(self, port: str) -> PortSecurityStatus:
        return PortSecurityStatus(
            secure_macs=tuple(sorted(self._secure.get(port, set()))),
            violations=self._violations.get(port, 0),
            last_violator=self._last_violator.get(port),
        )
