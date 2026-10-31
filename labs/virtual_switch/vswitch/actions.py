"""Use cases exposed to the presentation layer (the CLI).

Read use cases take the engine lock and return immutable view objects, so the
CLI never touches live engine state while frames are being switched.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from .domain import MacEntry, PortCounters, PortMode, SpanSession, StpConfig
from .mac import normalize_mac
from .switch import VirtualSwitch
from .vlan import format_vlan_list, parse_vlan_list, validate_vlan_id

TRUNK_LABEL = "trunk"


@dataclass(frozen=True)
class InterfaceView:
    name: str
    interface: str
    description: str
    status: str
    vlan: str
    mode: str
    err_reason: str | None
    counters: PortCounters


@dataclass(frozen=True)
class TrunkView:
    name: str
    native_vlan: int
    allowed_vlans: str


@dataclass(frozen=True)
class VlanView:
    vlan: int
    name: str
    ports: tuple[str, ...]


@dataclass(frozen=True)
class MacEntryView:
    entry: MacEntry
    age: float


@dataclass(frozen=True)
class StpPortView:
    name: str
    role: str
    state: str
    cost: int
    port_id: int


@dataclass(frozen=True)
class StpView:
    enabled: bool
    bridge_id: str
    root_id: str
    root_cost: int
    root_port: str | None
    is_root: bool
    timers: StpConfig | None
    ports: tuple[StpPortView, ...]


@dataclass(frozen=True)
class PortSecurityView:
    port: str
    max_macs: int
    current: int
    violations: int
    action: str
    last_violator: str | None


@dataclass(frozen=True)
class StormControlView:
    port: str
    limit_pps: int
    suppressed: int


class SwitchActions:
    def __init__(self, switch: VirtualSwitch) -> None:
        self._switch = switch

    @property
    def hostname(self) -> str:
        return self._switch.name

    # ------------------------------------------------------------------ show

    def mac_address_table(
        self, vlan: int | None = None, port: str | None = None
    ) -> list[MacEntryView]:
        with self._switch.locked():
            port_name = self._switch.port(port).name if port else None
            table = self._switch.mac_table
            return [
                MacEntryView(entry, table.age_of(entry))
                for entry in table.entries(vlan=vlan, port=port_name)
            ]

    def interfaces(self) -> list[InterfaceView]:
        with self._switch.locked():
            return [
                InterfaceView(
                    name=p.name,
                    interface=p.config.interface,
                    description=p.config.description,
                    status=p.status,
                    vlan=TRUNK_LABEL
                    if p.config.mode is PortMode.TRUNK
                    else str(p.config.access_vlan),
                    mode=p.config.mode.value,
                    err_reason=p.err_disabled_reason,
                    counters=replace(p.counters),
                )
                for p in self._switch.ports()
            ]

    def trunks(self) -> list[TrunkView]:
        with self._switch.locked():
            return [
                TrunkView(p.name, p.config.native_vlan, format_vlan_list(p.config.allowed_vlans))
                for p in self._switch.ports()
                if p.config.mode is PortMode.TRUNK
            ]

    def vlans(self) -> list[VlanView]:
        with self._switch.locked():
            ports = self._switch.ports()
            return [
                VlanView(
                    vlan,
                    name,
                    tuple(
                        p.name
                        for p in ports
                        if p.config.mode is PortMode.ACCESS and p.config.access_vlan == vlan
                    ),
                )
                for vlan, name in self._switch.vlans.items()
            ]

    def spanning_tree(self) -> StpView:
        with self._switch.locked():
            stp = self._switch.stp
            if stp is None:
                return StpView(False, "", "", 0, None, False, None, ())
            return StpView(
                enabled=True,
                bridge_id=str(stp.bridge_id),
                root_id=str(stp.root_id),
                root_cost=stp.root_cost,
                root_port=stp.root_port,
                is_root=stp.is_root,
                timers=stp.config,
                ports=tuple(
                    StpPortView(p.name, p.role.value, p.state.value, p.cost, p.port_id)
                    for p in stp.ports()
                ),
            )

    def port_security(self) -> list[PortSecurityView]:
        with self._switch.locked():
            views = []
            for port in self._switch.ports():
                settings = port.config.port_security
                if settings is None:
                    continue
                status = self._switch.port_security.status(port.name)
                views.append(
                    PortSecurityView(
                        port.name,
                        settings.max_macs,
                        len(status.secure_macs),
                        status.violations,
                        settings.violation.value,
                        status.last_violator,
                    )
                )
            return views

    def span_sessions(self) -> list[SpanSession]:
        with self._switch.locked():
            return list(self._switch.span_sessions)

    def storm_control(self) -> list[StormControlView]:
        with self._switch.locked():
            return [
                StormControlView(
                    p.name,
                    p.config.storm_control_pps,
                    self._switch.storm_control.suppressed(p.name),
                )
                for p in self._switch.ports()
                if p.config.storm_control_pps is not None
            ]

    # ------------------------------------------------------------- configure

    def shutdown(self, port: str) -> None:
        self._switch.shutdown(port)

    def no_shutdown(self, port: str) -> None:
        self._switch.no_shutdown(port)

    def create_vlan(self, vlan: int, name: str | None = None) -> None:
        self._switch.add_vlan(validate_vlan_id(vlan), name)

    def delete_vlan(self, vlan: int) -> None:
        self._switch.remove_vlan(vlan)

    def set_access_vlan(self, port: str, vlan: int) -> None:
        self._switch.set_access_vlan(port, vlan)

    def set_mode(self, port: str, mode: str) -> None:
        self._switch.set_mode(port, PortMode(mode))

    def set_allowed_vlans(self, port: str, vlan_list: str) -> None:
        self._switch.set_allowed_vlans(port, parse_vlan_list(vlan_list))

    def set_native_vlan(self, port: str, vlan: int) -> None:
        self._switch.set_native_vlan(port, vlan)

    def add_static_mac(self, mac: str, vlan: int, port: str) -> None:
        self._switch.add_static_mac(normalize_mac(mac), vlan, port)

    def remove_static_mac(self, mac: str, vlan: int) -> None:
        self._switch.remove_static_mac(mac, vlan)

    def clear_mac_table(self) -> int:
        return self._switch.clear_mac_table()

    def clear_counters(self) -> None:
        self._switch.clear_counters()
