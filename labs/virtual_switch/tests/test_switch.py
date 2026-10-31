from __future__ import annotations

from conftest import BROADCAST, MAC_A, MAC_B, MAC_C, FakeClock, access, frame, trunk

from vswitch.bpdu_codec import decode_bpdu, encode_bpdu
from vswitch.domain import (
    PortSecurityConfig,
    SpanDirection,
    SpanSession,
    StaticMac,
    StpConfig,
    ViolationMode,
)
from vswitch.frames import parse_frame
from vswitch.stp import Bpdu, BridgeId, PriorityVector


def three_access_ports():
    return [access("p1"), access("p2"), access("p3")]


class TestForwarding:
    def test_unknown_unicast_is_flooded_to_all_other_ports(self, make_switch) -> None:
        switch, io = make_switch(three_access_ports())
        io.inject("p1", frame(MAC_A, MAC_B))
        assert sorted(port for port, _ in io.sent) == ["p2", "p3"]

    def test_learned_destination_is_forwarded_to_one_port(self, make_switch) -> None:
        switch, io = make_switch(three_access_ports())
        io.inject("p2", frame(MAC_B, BROADCAST))
        io.clear()
        io.inject("p1", frame(MAC_A, MAC_B))
        assert [port for port, _ in io.sent] == ["p2"]
        assert switch.mac_table.lookup(MAC_A, 1) == "p1"

    def test_frame_to_same_segment_is_filtered(self, make_switch) -> None:
        switch, io = make_switch(three_access_ports())
        io.inject("p1", frame(MAC_B, BROADCAST))
        io.clear()
        io.inject("p1", frame(MAC_A, MAC_B))
        assert io.sent == []

    def test_broadcast_is_flooded(self, make_switch) -> None:
        switch, io = make_switch(three_access_ports())
        io.inject("p3", frame(MAC_C, BROADCAST))
        assert sorted(port for port, _ in io.sent) == ["p1", "p2"]

    def test_multicast_source_is_dropped(self, make_switch) -> None:
        switch, io = make_switch(three_access_ports())
        io.inject("p1", frame("01:00:5e:00:00:01", BROADCAST))
        assert io.sent == []
        assert switch.port("p1").counters.dropped == 1

    def test_static_entry_forwards_without_learning(self, make_switch) -> None:
        switch, io = make_switch(three_access_ports(), static_macs=[StaticMac(MAC_B, 1, "p3")])
        io.inject("p1", frame(MAC_A, MAC_B))
        assert [port for port, _ in io.sent] == ["p3"]

    def test_counters(self, make_switch) -> None:
        switch, io = make_switch(three_access_ports())
        raw = frame(MAC_A, BROADCAST)
        io.inject("p1", raw)
        counters = switch.port("p1").counters
        assert (counters.rx_frames, counters.rx_bytes, counters.rx_broadcast) == (1, len(raw), 1)
        assert switch.port("p2").counters.tx_frames == 1


class TestVlans:
    def test_vlans_are_isolated(self, make_switch) -> None:
        switch, io = make_switch(
            [access("p1", 10), access("p2", 10), access("p3", 20)], vlans={10: "A", 20: "B"}
        )
        io.inject("p1", frame(MAC_A, BROADCAST))
        assert [port for port, _ in io.sent] == ["p2"]

    def test_access_to_trunk_adds_tag_and_back_removes_it(self, make_switch) -> None:
        switch, io = make_switch([access("p1", 10), trunk("t1")], vlans={10: "A"})
        io.inject("p1", frame(MAC_A, BROADCAST))
        assert parse_frame(io.sent_on("t1")[0]).vlan_tag == 10
        io.clear()
        io.inject("t1", frame(MAC_B, MAC_A, vlan=10))
        assert io.sent_on("p1") == [frame(MAC_B, MAC_A)]

    def test_native_vlan_is_untagged_on_trunk(self, make_switch) -> None:
        switch, io = make_switch([access("p1", 1), trunk("t1", native_vlan=1)])
        io.inject("p1", frame(MAC_A, BROADCAST))
        assert io.sent_on("t1") == [frame(MAC_A, BROADCAST)]

    def test_trunk_drops_vlans_not_allowed(self, make_switch) -> None:
        switch, io = make_switch(
            [access("p1", 20), trunk("t1", allowed_vlans=frozenset({1, 10}))], vlans={20: "B"}
        )
        io.inject("p1", frame(MAC_A, BROADCAST))
        assert io.sent_on("t1") == []

    def test_frames_for_nonexistent_vlan_are_dropped(self, make_switch) -> None:
        switch, io = make_switch([trunk("t1"), trunk("t2")])
        io.inject("t1", frame(MAC_A, BROADCAST, vlan=300))
        assert io.sent == []

    def test_access_port_drops_tagged_frames(self, make_switch) -> None:
        switch, io = make_switch([access("p1", 10), access("p2", 10)], vlans={10: "A"})
        io.inject("p1", frame(MAC_A, BROADCAST, vlan=10))
        assert io.sent == []


class TestSecurityFeatures:
    def test_port_security_shutdown_err_disables_port(self, make_switch) -> None:
        secured = access("p1", port_security=PortSecurityConfig(1, ViolationMode.SHUTDOWN))
        switch, io = make_switch([secured, access("p2")])
        io.inject("p1", frame(MAC_A, BROADCAST))
        io.inject("p1", frame(MAC_B, BROADCAST))
        port = switch.port("p1")
        assert port.status == "err-disabled"
        assert switch.mac_table.entries(port="p1") == []
        io.clear()
        io.inject("p1", frame(MAC_A, BROADCAST))
        assert io.sent == []
        switch.no_shutdown("p1")
        assert switch.port("p1").is_up

    def test_storm_control_suppresses_excess_broadcasts(self, make_switch) -> None:
        switch, io = make_switch([access("p1", storm_control_pps=2), access("p2")])
        for _ in range(5):
            io.inject("p1", frame(MAC_A, BROADCAST))
        assert len(io.sent_on("p2")) == 2

    def test_bpdu_guard_err_disables_on_bpdu(self, make_switch) -> None:
        switch, io = make_switch([access("p1", bpdu_guard=True), access("p2")])
        vector = PriorityVector(BridgeId(0, MAC_B), 0, BridgeId(0, MAC_B), 0x8001)
        io.inject("p1", encode_bpdu(Bpdu(vector, 0, 20, 2, 15), MAC_B))
        assert switch.port("p1").err_disabled_reason == "bpduguard"

    def test_shutdown_port_neither_receives_nor_sends(self, make_switch) -> None:
        switch, io = make_switch(three_access_ports())
        switch.shutdown("p3")
        io.inject("p1", frame(MAC_A, BROADCAST))
        assert io.sent_on("p3") == []
        io.inject("p3", frame(MAC_C, BROADCAST))
        assert switch.mac_table.lookup(MAC_C, 1) is None


class TestSpan:
    def test_rx_and_tx_traffic_is_mirrored(self, make_switch) -> None:
        span = SpanSession(1, frozenset({"p1"}), "mon", SpanDirection.BOTH)
        switch, io = make_switch([access("p1"), access("p2"), access("mon")], span_sessions=[span])
        io.inject("p1", frame(MAC_A, BROADCAST))  # rx on p1
        io.inject("p2", frame(MAC_B, MAC_A))  # tx on p1
        assert io.sent_on("mon") == [frame(MAC_A, BROADCAST), frame(MAC_B, MAC_A)]

    def test_span_destination_is_not_a_normal_port(self, make_switch) -> None:
        span = SpanSession(1, frozenset({"p1"}), "mon", SpanDirection.TX)
        switch, io = make_switch([access("p1"), access("p2"), access("mon")], span_sessions=[span])
        io.inject("mon", frame(MAC_C, BROADCAST))
        assert io.sent == []


class TestStpIntegration:
    def test_ports_only_forward_after_listening_and_learning(
        self, make_switch, clock: FakeClock
    ) -> None:
        stp = StpConfig(hello_time=1, forward_delay=4, max_age=6)
        switch, io = make_switch([access("p1"), access("p2")], stp=stp)
        io.inject("p1", frame(MAC_A, BROADCAST))
        assert io.sent_on("p2") == []
        for _ in range(8):
            clock.advance(1)
            switch.tick()
        io.clear()
        io.inject("p1", frame(MAC_A, BROADCAST))
        assert len(io.sent_on("p2")) == 1

    def test_switch_emits_and_consumes_bpdus(self, make_switch, clock: FakeClock) -> None:
        switch, io = make_switch([access("p1"), access("p2")], stp=StpConfig())
        clock.advance(2)
        switch.tick()
        bpdus = [decode_bpdu(raw) for raw in io.sent_on("p1")]
        assert bpdus and bpdus[0] is not None
        assert bpdus[0].vector.root == switch.stp.bridge_id
        better = PriorityVector(BridgeId(0, MAC_B), 0, BridgeId(0, MAC_B), 0x8001)
        io.clear()
        io.inject("p1", encode_bpdu(Bpdu(better, 0, 20, 2, 15), MAC_B))
        assert switch.stp.root_port == "p1"
        clock.advance(2)
        switch.tick()
        relayed = decode_bpdu(io.sent_on("p2")[-1])
        assert relayed is not None
        assert relayed.vector.root == BridgeId(0, MAC_B)
        assert relayed.vector.root_cost == 19
