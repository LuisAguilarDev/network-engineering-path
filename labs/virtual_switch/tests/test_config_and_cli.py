from __future__ import annotations

import io
from pathlib import Path

import pytest
from conftest import BROADCAST, MAC_A, access, frame

from vswitch.actions import SwitchActions
from vswitch.cli import SwitchCli, match_keyword
from vswitch.config_loader import ConfigError, load_config, parse_config
from vswitch.domain import PortMode, ViolationMode

CONFIGS = Path(__file__).resolve().parent.parent / "configs"


class TestConfig:
    @pytest.mark.parametrize("name", ["single.toml", "stp-sw1.toml", "stp-sw2.toml"])
    def test_shipped_configs_load(self, name: str) -> None:
        config = load_config(CONFIGS / name)
        assert config.ports

    def test_single_config_features(self) -> None:
        config = load_config(CONFIGS / "single.toml")
        ports = {p.name: p for p in config.ports}
        assert ports["Gi0/4"].mode is PortMode.TRUNK
        assert ports["Gi0/1"].port_security is not None
        assert ports["Gi0/1"].port_security.violation is ViolationMode.RESTRICT
        assert config.span_sessions[0].destination == "Gi0/5"

    def test_access_vlans_are_auto_created(self) -> None:
        config = parse_config({"ports": [{"name": "p1", "interface": "e1", "access_vlan": 30}]})
        assert 30 in config.vlans

    @pytest.mark.parametrize(
        "data",
        [
            {},
            {"ports": [{"name": "p1", "interface": "e1"}, {"name": "p1", "interface": "e2"}]},
            {"ports": [{"name": "p1", "interface": "e1", "access_vlan": 5000}]},
            {
                "ports": [{"name": "p1", "interface": "e1"}],
                "span": [{"source_ports": ["p1"], "destination": "nope"}],
            },
        ],
    )
    def test_invalid_configs_are_rejected(self, data: dict) -> None:
        with pytest.raises(ConfigError):
            parse_config(data)


class TestCli:
    def _cli(self, make_switch):
        switch, wire = make_switch([access("Gi0/1"), access("Gi0/2")])
        out = io.StringIO()
        return SwitchCli(SwitchActions(switch), stdout=out), out, switch, wire

    def test_keyword_abbreviation(self) -> None:
        assert match_keyword("int", ("interfaces", "vlan")) == "interfaces"
        assert match_keyword("sh", ("show", "shutdown"), preferred=("show",)) == "show"
        with pytest.raises(ValueError, match="ambiguous"):
            match_keyword("s", ("show", "shutdown"))

    def test_show_mac_address_table(self, make_switch) -> None:
        cli, out, switch, wire = self._cli(make_switch)
        wire.inject("Gi0/1", frame(MAC_A, BROADCAST))
        cli.onecmd("sh mac add")
        assert "0000.0000.000a" in out.getvalue()
        assert "Total Mac Addresses: 1" in out.getvalue()

    def test_configuration_commands(self, make_switch) -> None:
        cli, out, switch, _ = self._cli(make_switch)
        cli.onecmd("vlan 10 USERS")
        cli.onecmd("switchport gi0/2 access vlan 10")
        cli.onecmd("shutdown Gi0/1")
        assert switch.port("Gi0/2").config.access_vlan == 10
        assert not switch.port("Gi0/1").is_up
        cli.onecmd("no shutdown Gi0/1")
        assert switch.port("Gi0/1").is_up
        cli.onecmd("show vlan")
        assert "USERS" in out.getvalue()

    def test_errors_are_reported_not_raised(self, make_switch) -> None:
        cli, out, *_ = self._cli(make_switch)
        cli.onecmd("shutdown Gi9/9")
        assert "% unknown interface" in out.getvalue()

    @pytest.mark.parametrize(
        "command",
        [
            "show interfaces",
            "show interfaces counters",
            "show interfaces trunk",
            "show spanning-tree",
            "show port-security",
            "show monitor",
            "show storm-control",
        ],
    )
    def test_every_show_command_renders(self, make_switch, command: str) -> None:
        cli, out, *_ = self._cli(make_switch)
        cli.onecmd(command)
        assert out.getvalue() and "%" not in out.getvalue()
