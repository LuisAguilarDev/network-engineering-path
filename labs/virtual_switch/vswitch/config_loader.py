"""Load and validate a switch configuration from a TOML file."""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .domain import (
    DEFAULT_BRIDGE_MAC,
    DEFAULT_MAC_AGING_SECONDS,
    DEFAULT_STP_BRIDGE_PRIORITY,
    DEFAULT_STP_PORT_COST,
    DEFAULT_STP_PORT_PRIORITY,
    DEFAULT_VLAN,
    PortConfig,
    PortMode,
    PortSecurityConfig,
    SpanDirection,
    SpanSession,
    StaticMac,
    StpConfig,
    SwitchConfig,
    ViolationMode,
)
from .mac import normalize_mac
from .vlan import validate_vlan_id

DEFAULT_SWITCH_NAME = "vSwitch"


class ConfigError(ValueError):
    pass


def load_config(path: Path) -> SwitchConfig:
    with path.open("rb") as handle:
        try:
            data = tomllib.load(handle)
        except tomllib.TOMLDecodeError as exc:
            raise ConfigError(f"{path}: {exc}") from exc
    return parse_config(data)


def parse_config(data: Mapping[str, Any]) -> SwitchConfig:
    try:
        return _parse(data)
    except (KeyError, TypeError, ValueError) as exc:
        if isinstance(exc, ConfigError):
            raise
        raise ConfigError(f"invalid configuration: {exc}") from exc


def _parse(data: Mapping[str, Any]) -> SwitchConfig:
    switch = data.get("switch", {})
    ports = [_parse_port(raw) for raw in data.get("ports", [])]
    if not ports:
        raise ConfigError("at least one [[ports]] entry is required")
    _ensure_unique("port name", [p.name for p in ports])
    _ensure_unique("interface", [p.interface for p in ports])

    vlans = {validate_vlan_id(int(v["id"])): str(v.get("name", "")) for v in data.get("vlans", [])}
    for port in ports:  # IOS auto-creates VLANs referenced by access ports
        if port.mode is PortMode.ACCESS:
            vlans.setdefault(port.access_vlan, "")

    port_names = {p.name for p in ports}
    statics = [_parse_static(raw, port_names) for raw in data.get("static_macs", [])]
    spans = [
        _parse_span(index, raw, port_names)
        for index, raw in enumerate(data.get("span", []), start=1)
    ]

    return SwitchConfig(
        name=str(switch.get("name", DEFAULT_SWITCH_NAME)),
        bridge_mac=normalize_mac(switch.get("mac", DEFAULT_BRIDGE_MAC)),
        mac_aging_time=float(switch.get("mac_aging_time", DEFAULT_MAC_AGING_SECONDS)),
        ports=ports,
        vlans={vlan: name for vlan, name in vlans.items() if vlan != DEFAULT_VLAN},
        stp=_parse_stp(data.get("stp", {})),
        static_macs=statics,
        span_sessions=spans,
    )


def _parse_port(raw: Mapping[str, Any]) -> PortConfig:
    allowed = raw.get("allowed_vlans")
    security = raw.get("port_security")
    storm = raw.get("storm_control_pps")
    return PortConfig(
        name=str(raw["name"]),
        interface=str(raw["interface"]),
        mode=PortMode(raw.get("mode", PortMode.ACCESS)),
        access_vlan=validate_vlan_id(int(raw.get("access_vlan", DEFAULT_VLAN))),
        native_vlan=validate_vlan_id(int(raw.get("native_vlan", DEFAULT_VLAN))),
        allowed_vlans=None
        if allowed is None
        else frozenset(validate_vlan_id(int(v)) for v in allowed),
        enabled=bool(raw.get("enabled", True)),
        description=str(raw.get("description", "")),
        port_security=None
        if security is None
        else PortSecurityConfig(
            max_macs=_positive(int(security.get("max_macs", 1)), "max_macs"),
            violation=ViolationMode(security.get("violation", ViolationMode.SHUTDOWN)),
        ),
        storm_control_pps=None if storm is None else _positive(int(storm), "storm_control_pps"),
        stp_cost=_positive(int(raw.get("stp_cost", DEFAULT_STP_PORT_COST)), "stp_cost"),
        stp_priority=int(raw.get("stp_priority", DEFAULT_STP_PORT_PRIORITY)),
        portfast=bool(raw.get("portfast", False)),
        bpdu_guard=bool(raw.get("bpdu_guard", False)),
    )


def _parse_stp(raw: Mapping[str, Any]) -> StpConfig:
    defaults = StpConfig()
    return StpConfig(
        enabled=bool(raw.get("enabled", defaults.enabled)),
        priority=int(raw.get("priority", DEFAULT_STP_BRIDGE_PRIORITY)),
        hello_time=float(raw.get("hello_time", defaults.hello_time)),
        forward_delay=float(raw.get("forward_delay", defaults.forward_delay)),
        max_age=float(raw.get("max_age", defaults.max_age)),
    )


def _parse_static(raw: Mapping[str, Any], port_names: set[str]) -> StaticMac:
    port = _known_port(str(raw["port"]), port_names)
    return StaticMac(normalize_mac(raw["mac"]), validate_vlan_id(int(raw["vlan"])), port)


def _parse_span(index: int, raw: Mapping[str, Any], port_names: set[str]) -> SpanSession:
    sources = frozenset(_known_port(str(name), port_names) for name in raw["source_ports"])
    destination = _known_port(str(raw["destination"]), port_names)
    if destination in sources:
        raise ConfigError(f"SPAN session {index}: destination cannot also be a source")
    return SpanSession(
        session_id=index,
        sources=sources,
        destination=destination,
        direction=SpanDirection(raw.get("direction", SpanDirection.BOTH)),
    )


def _known_port(name: str, port_names: set[str]) -> str:
    if name not in port_names:
        raise ConfigError(f"unknown port {name!r}")
    return name


def _positive(value: int, field_name: str) -> int:
    if value <= 0:
        raise ConfigError(f"{field_name} must be positive, got {value}")
    return value


def _ensure_unique(label: str, values: list[str]) -> None:
    duplicates = sorted({v for v in values if values.count(v) > 1})
    if duplicates:
        raise ConfigError(f"duplicate {label}: {', '.join(duplicates)}")
