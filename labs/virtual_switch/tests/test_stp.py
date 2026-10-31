from __future__ import annotations

from conftest import FakeClock

from vswitch.bpdu_codec import decode_bpdu, encode_bpdu
from vswitch.domain import StpConfig, StpRole, StpState
from vswitch.stp import Bpdu, BridgeId, PriorityVector, SpanningTree

FAST = StpConfig(hello_time=1, forward_delay=4, max_age=6)
LOW_MAC = "02:00:00:00:00:01"
HIGH_MAC = "02:00:00:00:00:02"


class Lab:
    """Two bridges joined by two parallel links (l1, l2): a classic layer-2 loop."""

    def __init__(self, clock: FakeClock) -> None:
        self.clock = clock
        self.queue: list[tuple[str, str, Bpdu]] = []
        self.sw1 = self._bridge("sw1", BridgeId(32768, LOW_MAC))
        self.sw2 = self._bridge("sw2", BridgeId(32768, HIGH_MAC))
        self.bridges = {"sw1": self.sw1, "sw2": self.sw2}
        for stp in self.bridges.values():
            for number, link in enumerate(("l1", "l2"), start=1):
                stp.add_port(link, number, cost=19, priority=128)
            for link in ("l1", "l2"):
                stp.set_port_enabled(link, True)
        self.deliver()

    def _bridge(self, name: str, bridge_id: BridgeId) -> SpanningTree:
        return SpanningTree(
            bridge_id, FAST, self.clock, lambda port, bpdu: self.queue.append((name, port, bpdu))
        )

    def deliver(self) -> None:
        while self.queue:
            sender, port, bpdu = self.queue.pop(0)
            peer = "sw2" if sender == "sw1" else "sw1"
            self.bridges[peer].receive(port, bpdu)

    def run(self, seconds: int) -> None:
        for _ in range(seconds):
            self.clock.advance(1)
            for stp in self.bridges.values():
                stp.tick()
            self.deliver()


def test_lowest_bridge_id_becomes_root(clock: FakeClock) -> None:
    lab = Lab(clock)
    assert lab.sw1.is_root
    assert lab.sw2.root_id == lab.sw1.bridge_id
    assert lab.sw2.root_port == "l1"  # tie broken by the lowest sender port id
    assert lab.sw2.root_cost == 19


def test_loop_is_broken_by_blocking_one_port(clock: FakeClock) -> None:
    lab = Lab(clock)
    roles = {p.name: p.role for p in lab.sw2.ports()}
    assert roles == {"l1": StpRole.ROOT, "l2": StpRole.ALTERNATE}
    assert lab.sw2.state("l2") is StpState.BLOCKING
    assert {p.role for p in lab.sw1.ports()} == {StpRole.DESIGNATED}


def test_ports_walk_listening_learning_forwarding(clock: FakeClock) -> None:
    lab = Lab(clock)
    assert lab.sw1.state("l1") is StpState.LISTENING
    lab.run(4)
    assert lab.sw1.state("l1") is StpState.LEARNING
    lab.run(4)
    assert lab.sw1.state("l1") is StpState.FORWARDING
    assert lab.sw2.state("l2") is StpState.BLOCKING


def test_failover_when_root_port_goes_down(clock: FakeClock) -> None:
    lab = Lab(clock)
    lab.run(10)
    lab.sw2.set_port_enabled("l1", False)
    lab.sw1.set_port_enabled("l1", False)
    lab.deliver()
    assert lab.sw2.root_port == "l2"
    lab.run(10)
    assert lab.sw2.state("l2") is StpState.FORWARDING


def test_stale_root_information_expires(clock: FakeClock) -> None:
    sent: list[Bpdu] = []
    stp = SpanningTree(BridgeId(32768, HIGH_MAC), FAST, clock, lambda _p, b: sent.append(b))
    stp.add_port("p1", 1, cost=19, priority=128)
    stp.set_port_enabled("p1", True)
    better = PriorityVector(BridgeId(4096, LOW_MAC), 0, BridgeId(4096, LOW_MAC), 0x8001)
    stp.receive("p1", Bpdu(better, 0, FAST.max_age, FAST.hello_time, FAST.forward_delay))
    assert not stp.is_root
    clock.advance(FAST.max_age)
    stp.tick()
    assert stp.is_root


def test_portfast_forwards_immediately(clock: FakeClock) -> None:
    stp = SpanningTree(BridgeId(32768, LOW_MAC), FAST, clock, lambda _p, _b: None)
    stp.add_port("edge", 1, cost=19, priority=128, portfast=True)
    stp.set_port_enabled("edge", True)
    assert stp.state("edge") is StpState.FORWARDING


def test_bpdu_wire_roundtrip() -> None:
    vector = PriorityVector(BridgeId(4096, LOW_MAC), 38, BridgeId(32768, HIGH_MAC), 0x8002)
    bpdu = Bpdu(vector, message_age=1, max_age=20, hello_time=2, forward_delay=15)
    assert decode_bpdu(encode_bpdu(bpdu, HIGH_MAC)) == bpdu
