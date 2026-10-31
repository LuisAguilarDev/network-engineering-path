from __future__ import annotations

from conftest import MAC_A, MAC_B, MAC_C, FakeClock, access

from vswitch.domain import PortSecurityConfig, ViolationMode
from vswitch.mac_table import MacAddressTable
from vswitch.port_security import PortSecurity, SecurityVerdict
from vswitch.storm_control import StormControl


class TestMacTable:
    def test_learn_lookup_and_move(self, clock: FakeClock) -> None:
        table = MacAddressTable(clock, aging_time=300)
        table.learn(MAC_A, 1, "p1")
        assert table.lookup(MAC_A, 1) == "p1"
        assert table.lookup(MAC_A, 2) is None  # tables are per VLAN
        table.learn(MAC_A, 1, "p2")
        assert table.lookup(MAC_A, 1) == "p2"

    def test_dynamic_entries_age_out(self, clock: FakeClock) -> None:
        table = MacAddressTable(clock, aging_time=300)
        table.learn(MAC_A, 1, "p1")
        clock.advance(299)
        assert table.age_out() == 0
        clock.advance(1)
        assert table.age_out() == 1
        assert table.lookup(MAC_A, 1) is None

    def test_static_entries_never_age_or_move(self, clock: FakeClock) -> None:
        table = MacAddressTable(clock, aging_time=10)
        table.add_static(MAC_A, 1, "p1")
        assert not table.learn(MAC_A, 1, "p2")
        clock.advance(100)
        table.age_out()
        assert table.lookup(MAC_A, 1) == "p1"

    def test_table_full(self, clock: FakeClock) -> None:
        table = MacAddressTable(clock, aging_time=300, max_entries=1)
        assert table.learn(MAC_A, 1, "p1")
        assert not table.learn(MAC_B, 1, "p1")

    def test_flush_by_port_keeps_statics(self, clock: FakeClock) -> None:
        table = MacAddressTable(clock, aging_time=300)
        table.learn(MAC_A, 1, "p1")
        table.add_static(MAC_B, 1, "p1")
        table.learn(MAC_C, 1, "p2")
        assert table.flush(port="p1") == 1
        assert [e.mac for e in table.entries()] == [MAC_B, MAC_C]


class TestPortSecurity:
    def _port(self, mode: ViolationMode, max_macs: int = 1):
        return access("p1", port_security=PortSecurityConfig(max_macs=max_macs, violation=mode))

    def test_allows_up_to_max_macs(self) -> None:
        security = PortSecurity()
        port = self._port(ViolationMode.RESTRICT, max_macs=2)
        assert security.check(port, MAC_A, 1) is SecurityVerdict.ALLOW
        assert security.check(port, MAC_B, 1) is SecurityVerdict.ALLOW
        assert security.check(port, MAC_A, 1) is SecurityVerdict.ALLOW

    def test_protect_drops_without_counting(self) -> None:
        security = PortSecurity()
        port = self._port(ViolationMode.PROTECT)
        security.check(port, MAC_A, 1)
        assert security.check(port, MAC_B, 1) is SecurityVerdict.DROP
        assert security.status("p1").violations == 0

    def test_restrict_drops_and_counts(self) -> None:
        security = PortSecurity()
        port = self._port(ViolationMode.RESTRICT)
        security.check(port, MAC_A, 1)
        assert security.check(port, MAC_B, 1) is SecurityVerdict.DROP
        assert security.status("p1").violations == 1
        assert security.status("p1").last_violator == MAC_B

    def test_shutdown_verdict(self) -> None:
        security = PortSecurity()
        port = self._port(ViolationMode.SHUTDOWN)
        security.check(port, MAC_A, 1)
        assert security.check(port, MAC_B, 1) is SecurityVerdict.SHUTDOWN


class TestStormControl:
    def test_limits_per_second_window(self, clock: FakeClock) -> None:
        storm = StormControl(clock)
        assert all(storm.allow("p1", 3) for _ in range(3))
        assert not storm.allow("p1", 3)
        assert storm.suppressed("p1") == 1
        clock.advance(1)
        assert storm.allow("p1", 3)

    def test_no_limit_configured(self, clock: FakeClock) -> None:
        storm = StormControl(clock)
        assert all(storm.allow("p1", None) for _ in range(1000))
