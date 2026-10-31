"""MAC address helpers."""

from __future__ import annotations

import re

MAC_HEX_DIGITS = 12
_HEX_ONLY = re.compile(r"^[0-9a-f]{12}$")
_SEPARATORS = str.maketrans("", "", ":-.")
_GROUP_BIT = 0x01


def normalize_mac(mac: str) -> str:
    """Return ``mac`` as lowercase colon notation. Accepts colon, dash and Cisco dot notation."""
    digits = mac.strip().lower().translate(_SEPARATORS)
    if not _HEX_ONLY.match(digits):
        raise ValueError(f"invalid MAC address: {mac!r}")
    return ":".join(digits[i : i + 2] for i in range(0, MAC_HEX_DIGITS, 2))


def bytes_to_mac(raw: bytes) -> str:
    return ":".join(f"{octet:02x}" for octet in raw)


def is_multicast(mac: str) -> bool:
    """True for group addresses (I/G bit set). Broadcast is a special multicast."""
    return int(mac[:2], 16) & _GROUP_BIT == _GROUP_BIT


def to_cisco(mac: str) -> str:
    """Render ``aa:bb:cc:dd:ee:ff`` as ``aabb.ccdd.eeff`` like IOS does."""
    digits = mac.replace(":", "")
    return ".".join(digits[i : i + 4] for i in range(0, MAC_HEX_DIGITS, 4))
