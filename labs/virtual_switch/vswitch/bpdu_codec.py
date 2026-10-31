"""Translate between STP domain BPDUs and wire bytes using scapy."""

from __future__ import annotations

from scapy.layers.l2 import LLC, STP, Dot3, Ether

from .domain import STP_MULTICAST_MAC
from .mac import normalize_mac
from .stp import Bpdu, BridgeId, PriorityVector

STP_LLC_SAP = 0x42
LLC_UNNUMBERED_INFO = 0x03
CONFIG_BPDU_TYPE = 0x00


def encode_bpdu(bpdu: Bpdu, src_mac: str) -> bytes:
    vector = bpdu.vector
    frame = (
        Dot3(dst=STP_MULTICAST_MAC, src=src_mac)
        / LLC(dsap=STP_LLC_SAP, ssap=STP_LLC_SAP, ctrl=LLC_UNNUMBERED_INFO)
        / STP(
            bpdutype=CONFIG_BPDU_TYPE,
            rootid=vector.root.priority,
            rootmac=vector.root.mac,
            pathcost=vector.root_cost,
            bridgeid=vector.bridge.priority,
            bridgemac=vector.bridge.mac,
            portid=vector.port_id,
            age=bpdu.message_age,
            maxage=bpdu.max_age,
            hellotime=bpdu.hello_time,
            fwddelay=bpdu.forward_delay,
        )
    )
    return bytes(frame)


def decode_bpdu(raw: bytes) -> Bpdu | None:
    """Return the configuration BPDU carried by ``raw``, or None (TCN or not STP)."""
    stp = Ether(raw).getlayer(STP)
    if stp is None or stp.bpdutype != CONFIG_BPDU_TYPE:
        return None
    return Bpdu(
        vector=PriorityVector(
            root=BridgeId(stp.rootid, normalize_mac(stp.rootmac)),
            root_cost=stp.pathcost,
            bridge=BridgeId(stp.bridgeid, normalize_mac(stp.bridgemac)),
            port_id=stp.portid,
        ),
        message_age=float(stp.age),
        max_age=float(stp.maxage),
        hello_time=float(stp.hellotime),
        forward_delay=float(stp.fwddelay),
    )
