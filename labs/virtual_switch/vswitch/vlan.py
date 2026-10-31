"""VLAN database and 802.1Q ingress/egress rules."""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from .domain import DEFAULT_VLAN, MAX_VLAN, MIN_VLAN, PortConfig, PortMode
from .frames import tag_frame

DEFAULT_VLAN_NAME = "default"
ALL_VLANS_KEYWORD = "all"


def validate_vlan_id(vlan: int) -> int:
    if not MIN_VLAN <= vlan <= MAX_VLAN:
        raise ValueError(f"VLAN {vlan} out of range ({MIN_VLAN}-{MAX_VLAN})")
    return vlan


def parse_vlan_list(text: str) -> frozenset[int] | None:
    """Parse ``"1,10,20-30"`` into a set of VLAN IDs; ``"all"`` returns None."""
    if text.strip().lower() == ALL_VLANS_KEYWORD:
        return None
    vlans: set[int] = set()
    for chunk in text.split(","):
        start, _, end = chunk.strip().partition("-")
        first = validate_vlan_id(int(start))
        last = validate_vlan_id(int(end)) if end else first
        if last < first:
            raise ValueError(f"invalid VLAN range: {chunk.strip()!r}")
        vlans.update(range(first, last + 1))
    return frozenset(vlans)


def format_vlan_list(vlans: Iterable[int] | None) -> str:
    """Compress ``{1, 2, 3, 10}`` into ``"1-3,10"``; None renders as ``"all"``."""
    if vlans is None:
        return ALL_VLANS_KEYWORD
    ordered = sorted(vlans)
    if not ordered:
        return "none"
    ranges: list[str] = []
    start = prev = ordered[0]
    for vlan in ordered[1:] + [None]:
        if vlan is not None and vlan == prev + 1:
            prev = vlan
            continue
        ranges.append(str(start) if start == prev else f"{start}-{prev}")
        if vlan is not None:
            start = prev = vlan
    return ",".join(ranges)


class VlanDatabase:
    """The set of VLANs that exist on the switch. VLAN 1 always exists."""

    def __init__(self, vlans: Mapping[int, str] | None = None) -> None:
        self._vlans: dict[int, str] = {DEFAULT_VLAN: DEFAULT_VLAN_NAME}
        for vlan, name in (vlans or {}).items():
            self.add(vlan, name)

    def add(self, vlan: int, name: str | None = None) -> None:
        validate_vlan_id(vlan)
        self._vlans[vlan] = name or self._vlans.get(vlan) or f"VLAN{vlan:04d}"

    def remove(self, vlan: int) -> None:
        if vlan == DEFAULT_VLAN:
            raise ValueError("default VLAN 1 cannot be deleted")
        if vlan not in self._vlans:
            raise ValueError(f"VLAN {vlan} does not exist")
        del self._vlans[vlan]

    def exists(self, vlan: int) -> bool:
        return vlan in self._vlans

    def items(self) -> list[tuple[int, str]]:
        return sorted(self._vlans.items())


def ingress_vlan(port: PortConfig, vlan_tag: int | None) -> int | None:
    """Return the VLAN a received frame belongs to, or None if the port must drop it."""
    if port.mode is PortMode.ACCESS:
        return port.access_vlan if vlan_tag is None else None
    vlan = port.native_vlan if vlan_tag is None else vlan_tag
    return vlan if port.carries_vlan(vlan) else None


def egress_frame(port: PortConfig, vlan: int, untagged: bytes) -> bytes | None:
    """Return the frame as it must leave ``port``, or None if the port does not carry ``vlan``."""
    if not port.carries_vlan(vlan):
        return None
    if port.mode is PortMode.ACCESS or vlan == port.native_vlan:
        return untagged
    return tag_frame(untagged, vlan)
