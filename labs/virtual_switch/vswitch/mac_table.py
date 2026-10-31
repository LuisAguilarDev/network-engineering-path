"""MAC address table (CAM) with dynamic learning, static entries and aging."""

from __future__ import annotations

import logging

from .domain import MacEntry
from .gateways import Clock

logger = logging.getLogger(__name__)

DEFAULT_MAX_ENTRIES = 8192
NO_AGING = 0.0

MacKey = tuple[str, int]


class MacAddressTable:
    def __init__(
        self, clock: Clock, aging_time: float, max_entries: int = DEFAULT_MAX_ENTRIES
    ) -> None:
        self._clock = clock
        self.aging_time = aging_time
        self._max_entries = max_entries
        self._entries: dict[MacKey, MacEntry] = {}

    def __len__(self) -> int:
        return len(self._entries)

    def learn(self, mac: str, vlan: int, port: str) -> bool:
        """Record that ``mac`` lives behind ``port``. Returns False if it cannot be stored."""
        key = (mac, vlan)
        current = self._entries.get(key)
        if current is not None and current.static:
            return False
        if current is None and len(self._entries) >= self._max_entries:
            logger.warning("MAC table full, not learning %s on vlan %d", mac, vlan)
            return False
        if current is not None and current.port != port:
            logger.info("MAC move: %s vlan %d %s -> %s", mac, vlan, current.port, port)
        self._entries[key] = MacEntry(mac, vlan, port, static=False, last_seen=self._clock.now())
        return True

    def add_static(self, mac: str, vlan: int, port: str) -> None:
        self._entries[(mac, vlan)] = MacEntry(
            mac, vlan, port, static=True, last_seen=self._clock.now()
        )

    def remove_static(self, mac: str, vlan: int) -> bool:
        entry = self._entries.get((mac, vlan))
        if entry is None or not entry.static:
            return False
        del self._entries[(mac, vlan)]
        return True

    def lookup(self, mac: str, vlan: int) -> str | None:
        entry = self._entries.get((mac, vlan))
        return entry.port if entry else None

    def age_out(self) -> int:
        """Remove dynamic entries not refreshed within the aging time (0 disables aging)."""
        if self.aging_time <= NO_AGING:
            return 0
        cutoff = self._clock.now() - self.aging_time
        stale = [k for k, e in self._entries.items() if not e.static and e.last_seen <= cutoff]
        for key in stale:
            del self._entries[key]
        return len(stale)

    def flush(
        self, *, port: str | None = None, vlan: int | None = None, include_static: bool = False
    ) -> int:
        doomed = [
            key
            for key, entry in self._entries.items()
            if (include_static or not entry.static)
            and (port is None or entry.port == port)
            and (vlan is None or entry.vlan == vlan)
        ]
        for key in doomed:
            del self._entries[key]
        return len(doomed)

    def entries(self, *, vlan: int | None = None, port: str | None = None) -> list[MacEntry]:
        selected = (
            e
            for e in self._entries.values()
            if (vlan is None or e.vlan == vlan) and (port is None or e.port == port)
        )
        return sorted(selected, key=lambda e: (e.vlan, e.mac))

    def age_of(self, entry: MacEntry) -> float:
        return self._clock.now() - entry.last_seen
