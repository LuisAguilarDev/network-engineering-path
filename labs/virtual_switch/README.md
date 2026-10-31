# Lab — Virtual Layer 2 Switch in Python (scapy)

> **Domain:** 2. Network Access · **Tool:** Python 3.12 + scapy, Linux namespaces, Dev Container · **Date:** 2026-10-30

## Objective

Build a working Ethernet switch in software to understand what a Catalyst does with every frame:
MAC learning, flooding, filtering, VLANs, 802.1Q trunks, Spanning Tree, port security, storm
control and SPAN. It switches real traffic between Linux network namespaces and has an
IOS-style CLI (`show mac address-table`, `show spanning-tree`, ...).

## Features

| Feature | What it does | CCNA topic |
|---------|--------------|------------|
| MAC learning | Learns source MACs per VLAN, detects MAC moves | Switching concepts |
| Forward / filter / flood | Known unicast → one port, same segment → dropped, unknown unicast / broadcast / multicast → flooded | Switching concepts |
| MAC aging | Dynamic entries expire after `mac_aging_time` (default 300 s, 0 = never) | MAC table |
| Static MACs | Entries that never age or move | MAC table |
| VLANs | VLAN database; frames for a VLAN that does not exist are dropped | VLANs |
| Access ports | Untagged frames in one VLAN; tagged frames dropped | VLANs |
| 802.1Q trunks | Tagging, native VLAN (untagged), allowed VLAN list | Trunking |
| STP (802.1D) | Root election, root/designated/alternate roles, blocking → listening → learning → forwarding, hello and max-age timers | Spanning Tree |
| PortFast + BPDU Guard | Edge ports forward at once; a BPDU on a guarded port err-disables it | STP features |
| Port security | Max MACs per port, violation modes `protect` / `restrict` / `shutdown` (err-disable) | Security fundamentals |
| Storm control | Caps broadcast + multicast frames per second per port | Security / stability |
| SPAN | Mirrors rx / tx / both of source ports to a monitor port | Troubleshooting |
| Counters | Per-port in/out frames and octets, broadcast, multicast, drops | Troubleshooting |
| `shutdown` / `no shutdown` | Admin state; `no shutdown` also recovers err-disabled ports | Interface config |

Not implemented: RSTP/PVST+ (one STP instance for all VLANs), topology change notifications,
LACP/EtherChannel, voice VLAN, CDP/LLDP, routing (SVIs).

## Topology

`scripts/topology.py up single` builds:

```
  h1 10.0.10.1  ── Gi0/1 (access VLAN 10, port-security, BPDU guard, storm control)
  h2 10.0.10.2  ── Gi0/2 (access VLAN 10)
  h3 10.0.20.3  ── Gi0/3 (access VLAN 20)                                  vSW1
  h4 eth0.10 10.0.10.4 / eth0.20 10.0.20.4 ── Gi0/4 (802.1Q trunk 1,10,20)
  h5 sniffer    ── Gi0/5 (SPAN destination for Gi0/1)
```

`scripts/topology.py up stp` builds a loop on purpose:

```
  h1 10.0.1.1 ── Gi0/1 [vSW1 root, prio 4096] Gi0/23 ══ Gi0/23 [vSW2] Gi0/1 ── h2 10.0.1.2
                                              Gi0/24 ══ Gi0/24 (alternate, blocking)
```

Each host is a network namespace; each cable is a veth pair. The switch binds a scapy layer-2
socket to the switch end of each cable.

## Architecture

```
vswitch/
  cli.py            Presentation: IOS-style shell (cmd.Cmd), abbreviations like "sh mac add"
  actions.py        Use cases: show/configure operations returning immutable views
  switch.py         Forwarding engine (the frame pipeline below)
  mac_table.py      MAC address table with aging and static entries
  vlan.py           VLAN database + 802.1Q ingress/egress rules
  stp.py            802.1D state machine (pure logic)
  port_security.py  Secure MAC limits and violation handling
  storm_control.py  Per-second broadcast/multicast limiter
  frames.py         Raw Ethernet / 802.1Q header parsing and tagging
  bpdu_codec.py     BPDU <-> bytes with scapy (Dot3 / LLC / STP layers)
  gateways.py       FrameIO and Clock interfaces
  adapters/         scapy_io (real interfaces), memory_io (tests), system_clock
  config_loader.py  TOML config loading and validation
  app.py            Composition root (wires everything, runs the 1 s ticker)
```

The engine depends only on the `FrameIO` and `Clock` interfaces, so the whole switch, STP
included, is unit tested with an in-memory wire and a fake clock. No root access needed.

Frame pipeline (`switch.py`):

```
port up? → parse → BPDU? (to STP / BPDU guard) → SPAN rx → VLAN ingress → STP can learn?
→ port security → learn source MAC → STP forwarding? → storm control
→ forward / filter / flood → VLAN egress (tag / untag) → SPAN tx
```

## Configuration Steps

### Step 1 — Open the Dev Container

Requires Docker and VS Code with the *Dev Containers* extension. Open **this folder**
(`labs/virtual_switch`) in VS Code and run **Dev Containers: Reopen in Container**.

The container (`.devcontainer/`) gives you Python 3.12, scapy, pytest, ruff, mypy, iproute2,
tcpdump, tshark, ethtool, arping, and these VS Code extensions: Python, Pylance, Python Debugger,
Python Environments, Ruff, Mypy, Pylint, Flake8, Black, isort, Jupyter, autoDocstring,
Python Indent, Even Better TOML. It runs `privileged` because raw sockets and network namespaces
need it. That is fine for a throwaway lab container and wrong anywhere else.

The test suite runs automatically after the container is created.

### Step 2 — Build the wiring

```bash
sudo python scripts/topology.py up single
```

### Step 3 — Start the switch

```bash
sudo python -m vswitch --config configs/single.toml --log-level INFO --log-file vswitch.log
```

Use `--no-cli` to run headless. Open a second terminal for the hosts.

### Step 4 — Generate traffic

```bash
sudo ip netns exec h1 ping -c3 10.0.10.2          # same VLAN, access to access
sudo ip netns exec h1 ping -c3 10.0.10.4          # VLAN 10 across the trunk (tagged)
sudo ip netns exec h3 ping -c3 10.0.20.4          # VLAN 20 across the trunk (tagged)
sudo ip netns exec h5 tcpdump -nei eth0           # watch the SPAN copy of Gi0/1
sudo ip netns exec h4 tcpdump -nei eth0 -c5 vlan  # see the 802.1Q tags on the trunk
```

The trunk Gi0/4 has no PortFast, so it needs about 8 s (listening + learning with
`forward_delay = 4`) before it forwards.

### Step 5 — STP lab

```bash
sudo python scripts/topology.py down single
sudo python scripts/topology.py up stp
sudo python -m vswitch -c configs/stp-sw1.toml      # terminal 1
sudo python -m vswitch -c configs/stp-sw2.toml      # terminal 2
sudo ip netns exec h1 ping 10.0.1.2                 # terminal 3
```

On vSW2, `show spanning-tree` shows Gi0/23 as root port and Gi0/24 as alternate/blocking.
Run `shutdown Gi0/23` on vSW2 and watch Gi0/24 take over after listening and learning.

### CLI reference

| Command | Purpose |
|---------|---------|
| `show mac address-table [vlan N \| interface P]` | MAC table with type and age |
| `show interfaces [status \| counters \| trunk]` | Port status, counters, trunk details |
| `show vlan` | VLANs and their access ports |
| `show spanning-tree` | Root, bridge ID, timers, port roles and states |
| `show port-security` | Limits, current MACs, violations, last violator |
| `show monitor` / `show storm-control` | SPAN sessions / storm suppression |
| `vlan N [name]` / `no vlan N` | Create / delete a VLAN |
| `switchport P mode access\|trunk` | Port mode |
| `switchport P access vlan N` | Access VLAN (auto-creates it) |
| `switchport P trunk allowed vlan 1,10,20-30\|all` | Trunk allowed list |
| `switchport P trunk native vlan N` | Native VLAN |
| `mac static M vlan N interface P` / `no mac static M vlan N` | Static entries |
| `shutdown P` / `no shutdown P` | Admin down / up (recovers err-disabled) |
| `clear mac address-table` / `clear counters` | Reset dynamic entries / counters |
| `exit` | Stop the switch |

Keywords can be abbreviated like on IOS: `sh int cou`, `sh span`, `sw gi0/2 acc vlan 20`.

## Verification

```text
vSW1# show vlan
VLAN  Name     Status  Ports
----  -------  ------  ------------
1     default  active  Gi0/5
10    USERS    active  Gi0/1, Gi0/2
20    SERVERS  active  Gi0/3

vSW2# show spanning-tree
Spanning tree enabled protocol ieee
  Root ID    4096.02:00:00:00:00:01
             Cost 19, Port Gi0/23
  Bridge ID  32768.02:00:00:00:00:02
  Hello Time 1s  Max Age 6s  Forward Delay 4s

Interface  Role        State       Cost  Prio.Nbr
---------  ----------  ----------  ----  --------
Gi0/1      designated  forwarding  19    128.1
Gi0/23     root        forwarding  19    128.2
Gi0/24     alternate   blocking    19    128.3
```

Automated checks:

```bash
python -m pytest -q        # 75 unit tests: engine, VLANs, STP, security, CLI, config
ruff check . && mypy vswitch scripts
```

An end-to-end run on real veth interfaces in this container confirmed: same-VLAN pings work,
both VLANs cross the trunk tagged, VLAN 10 and VLAN 20 hosts cannot reach each other, SPAN copies
Gi0/1 traffic to h5, and in the STP topology vSW2 blocks Gi0/24 so broadcasts do not storm.

## Troubleshooting

| Symptom | Root cause | Fix |
|---------|------------|-----|
| `apt-get update` fails building the container (`NO_PUBKEY` for yarnpkg) | Base image ships a Yarn repo with an expired key | Dockerfile removes `yarn.list` before `apt-get update` |
| `error: raw sockets need root` | Raw `AF_PACKET` sockets require `CAP_NET_RAW` | Run with `sudo` |
| `No such device` on start | Topology not built | `sudo python scripts/topology.py up single` |
| Pings over the trunk fail for the first seconds | Port is in STP listening/learning | Wait `2 × forward_delay` or set `portfast = true` |
| A port shows `err-disabled (psecure-violation)` | More source MACs than `max_macs` with `violation = "shutdown"` | Fix the cause, then `no shutdown <port>` |
| TCP works badly but ping works | veth checksum/GRO offloads hand raw sockets odd frames | `topology.py` disables offloads with `ethtool -K` |

## Lessons Learned

- A switch decides on two addresses only: learn from the **source**, forward on the **destination**.
- MAC tables are per VLAN: the same MAC can live on different ports in different VLANs.
- The native VLAN is the only untagged VLAN on a trunk, so a mismatch silently merges VLANs.
- STP does not stop loops by "detecting" them. It builds a tree and blocks every port that
  is not root or designated, before any data flows (listening and learning).
- PortFast skips that wait, which is why it belongs only on edge ports, ideally with BPDU Guard.
- Keeping logic behind interfaces (`FrameIO`, `Clock`) made STP timers testable in milliseconds.

## Files

- `vswitch/` — the switch package (`python -m vswitch`)
- `configs/` — `single.toml`, `stp-sw1.toml`, `stp-sw2.toml`
- `scripts/topology.py` — builds/tears down namespaces and veth cables
- `tests/` — pytest suite
- `.devcontainer/` — Dockerfile and VS Code dev container definition
- `.vscode/launch.json` — debug the switch (with sudo) or the tests
