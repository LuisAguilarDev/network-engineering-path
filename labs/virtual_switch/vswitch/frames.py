"""Ethernet II / IEEE 802.1Q header handling on raw frame bytes.

Working on bytes (instead of scapy layers) keeps tagging lossless for every
frame type, including 802.3/LLC frames such as BPDUs.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

from .mac import bytes_to_mac

MAC_LEN = 6
ETHERTYPE_OFFSET = 2 * MAC_LEN
ETH_HEADER_LEN = ETHERTYPE_OFFSET + 2
DOT1Q_TAG_LEN = 4
TPID_DOT1Q = 0x8100
VLAN_ID_MASK = 0x0FFF
PRIORITY_TAG_VLAN = 0  # 802.1p priority-only tag: the frame belongs to the native VLAN


@dataclass(frozen=True)
class ParsedFrame:
    dst: str
    src: str
    vlan_tag: int | None
    untagged: bytes


def parse_frame(raw: bytes) -> ParsedFrame:
    """Split a frame into addresses, optional VLAN tag and its untagged form."""
    if len(raw) < ETH_HEADER_LEN:
        raise ValueError("frame is shorter than an Ethernet header")
    dst = bytes_to_mac(raw[:MAC_LEN])
    src = bytes_to_mac(raw[MAC_LEN:ETHERTYPE_OFFSET])
    (ethertype,) = struct.unpack_from("!H", raw, ETHERTYPE_OFFSET)
    if ethertype != TPID_DOT1Q:
        return ParsedFrame(dst, src, None, raw)
    if len(raw) < ETH_HEADER_LEN + DOT1Q_TAG_LEN:
        raise ValueError("truncated 802.1Q tag")
    (tci,) = struct.unpack_from("!H", raw, ETH_HEADER_LEN)
    vlan = tci & VLAN_ID_MASK
    untagged = raw[:ETHERTYPE_OFFSET] + raw[ETHERTYPE_OFFSET + DOT1Q_TAG_LEN :]
    return ParsedFrame(dst, src, None if vlan == PRIORITY_TAG_VLAN else vlan, untagged)


def tag_frame(untagged: bytes, vlan: int) -> bytes:
    """Insert an 802.1Q tag right after the source MAC."""
    tag = struct.pack("!HH", TPID_DOT1Q, vlan & VLAN_ID_MASK)
    return untagged[:ETHERTYPE_OFFSET] + tag + untagged[ETHERTYPE_OFFSET:]
