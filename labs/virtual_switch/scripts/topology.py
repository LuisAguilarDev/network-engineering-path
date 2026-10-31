#!/usr/bin/env python3
"""Build or tear down the lab wiring with Linux network namespaces and veth pairs.

Each "host" is a network namespace with one interface (eth0). The other end of
its veth cable stays in the main namespace, where the virtual switch binds to it.

    sudo python scripts/topology.py up single     # 5 hosts on one switch
    sudo python scripts/topology.py up stp        # 2 switches joined by 2 links (a loop)
    sudo python scripts/topology.py down single
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

PROC_IPV6_CONF = Path("/proc/sys/net/ipv6/conf")
# Offloads make veth hand over oversized (GRO) or unchecksummed (TX) frames to
# raw sockets; turning them off keeps every frame a real, valid Ethernet frame.
OFFLOADS = ("rx", "off", "tx", "off", "tso", "off", "gso", "off", "gro", "off")


@dataclass(frozen=True)
class SubInterface:
    vlan: int
    address: str


@dataclass(frozen=True)
class Host:
    namespace: str
    switch_side: str
    address: str | None
    subinterfaces: tuple[SubInterface, ...] = ()


@dataclass(frozen=True)
class Topology:
    hosts: tuple[Host, ...]
    links: tuple[tuple[str, str], ...] = field(default=())  # switch-to-switch cables


TOPOLOGIES: dict[str, Topology] = {
    "single": Topology(
        hosts=(
            Host("h1", "sw-p1", "10.0.10.1/24"),
            Host("h2", "sw-p2", "10.0.10.2/24"),
            Host("h3", "sw-p3", "10.0.20.3/24"),
            Host(
                "h4",
                "sw-p4",
                None,
                (SubInterface(10, "10.0.10.4/24"), SubInterface(20, "10.0.20.4/24")),
            ),
            Host("h5", "sw-p5", None),  # SPAN sniffer: no IP needed
        )
    ),
    "stp": Topology(
        hosts=(Host("h1", "s1-p1", "10.0.1.1/24"), Host("h2", "s2-p1", "10.0.1.2/24")),
        links=(("s1-l1", "s2-l1"), ("s1-l2", "s2-l2")),
    ),
}


def run(*command: str, check: bool = True) -> None:
    print("+", " ".join(command))
    subprocess.run(command, check=check)


def in_ns(namespace: str, *command: str) -> None:
    run("ip", "netns", "exec", namespace, *command)


def prepare_switch_side(interface: str) -> None:
    """Quiet the switch-facing interface: no IPv6 chatter, no offloads, link up."""
    (PROC_IPV6_CONF / interface / "disable_ipv6").write_text("1")
    run("ethtool", "-K", interface, *OFFLOADS, check=False)
    run("ip", "link", "set", interface, "up")


def build_host(host: Host) -> None:
    run("ip", "netns", "add", host.namespace)
    run(
        "ip",
        "link",
        "add",
        host.switch_side,
        "type",
        "veth",
        "peer",
        "name",
        "eth0",
        "netns",
        host.namespace,
    )
    prepare_switch_side(host.switch_side)
    in_ns(host.namespace, "ip", "link", "set", "lo", "up")
    in_ns(host.namespace, "ethtool", "-K", "eth0", *OFFLOADS)
    in_ns(host.namespace, "ip", "link", "set", "eth0", "up")
    if host.address:
        in_ns(host.namespace, "ip", "addr", "add", host.address, "dev", "eth0")
    for sub in host.subinterfaces:
        name = f"eth0.{sub.vlan}"
        in_ns(
            host.namespace,
            "ip",
            "link",
            "add",
            "link",
            "eth0",
            "name",
            name,
            "type",
            "vlan",
            "id",
            str(sub.vlan),
        )
        in_ns(host.namespace, "ip", "addr", "add", sub.address, "dev", name)
        in_ns(host.namespace, "ip", "link", "set", name, "up")


def build_link(left: str, right: str) -> None:
    run("ip", "link", "add", left, "type", "veth", "peer", "name", right)
    prepare_switch_side(left)
    prepare_switch_side(right)


def up(topology: Topology) -> None:
    for host in topology.hosts:
        build_host(host)
    for left, right in topology.links:
        build_link(left, right)


def down(topology: Topology) -> None:
    # Deleting a namespace destroys its veth end, and a veth pair dies with either end.
    for host in topology.hosts:
        run("ip", "netns", "del", host.namespace, check=False)
    for left, _ in topology.links:
        run("ip", "link", "del", left, check=False)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("action", choices=("up", "down"))
    parser.add_argument("topology", choices=sorted(TOPOLOGIES))
    args = parser.parse_args()
    topology = TOPOLOGIES[args.topology]
    try:
        (up if args.action == "up" else down)(topology)
    except (subprocess.CalledProcessError, OSError) as exc:
        print(
            f"error: {exc} (run as root; use 'down' to clean up a partial build)", file=sys.stderr
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
