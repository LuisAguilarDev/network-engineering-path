from __future__ import annotations

import pytest
from conftest import MAC_A, MAC_B, access, frame, trunk

from vswitch.frames import parse_frame, tag_frame
from vswitch.mac import is_multicast, normalize_mac, to_cisco
from vswitch.vlan import (
    VlanDatabase,
    egress_frame,
    format_vlan_list,
    ingress_vlan,
    parse_vlan_list,
)


class TestMac:
    @pytest.mark.parametrize("raw", ["AA:BB:CC:DD:EE:FF", "aa-bb-cc-dd-ee-ff", "aabb.ccdd.eeff"])
    def test_normalizes_every_notation(self, raw: str) -> None:
        assert normalize_mac(raw) == "aa:bb:cc:dd:ee:ff"

    def test_rejects_garbage(self) -> None:
        with pytest.raises(ValueError):
            normalize_mac("not-a-mac")

    def test_multicast_bit(self) -> None:
        assert is_multicast("ff:ff:ff:ff:ff:ff")
        assert is_multicast("01:00:5e:00:00:01")
        assert not is_multicast(MAC_A)

    def test_cisco_format(self) -> None:
        assert to_cisco("aa:bb:cc:dd:ee:ff") == "aabb.ccdd.eeff"


class TestFrames:
    def test_untagged_frame(self) -> None:
        raw = frame(MAC_A, MAC_B)
        parsed = parse_frame(raw)
        assert (parsed.src, parsed.dst, parsed.vlan_tag) == (MAC_A, MAC_B, None)
        assert parsed.untagged == raw

    def test_tag_roundtrip(self) -> None:
        untagged = frame(MAC_A, MAC_B)
        tagged = tag_frame(untagged, 10)
        assert tagged == frame(MAC_A, MAC_B, vlan=10)
        parsed = parse_frame(tagged)
        assert parsed.vlan_tag == 10
        assert parsed.untagged == untagged

    def test_priority_tag_means_untagged(self) -> None:
        assert parse_frame(frame(MAC_A, MAC_B, vlan=0)).vlan_tag is None

    def test_runt_frame_rejected(self) -> None:
        with pytest.raises(ValueError):
            parse_frame(b"\x00" * 10)


class TestVlanRules:
    def test_access_port_classifies_untagged_and_drops_tagged(self) -> None:
        port = access("p1", vlan=10)
        assert ingress_vlan(port, None) == 10
        assert ingress_vlan(port, 10) is None

    def test_trunk_uses_tag_or_native_and_enforces_allowed_list(self) -> None:
        port = trunk("t1", native_vlan=99, allowed_vlans=frozenset({10, 99}))
        assert ingress_vlan(port, 10) == 10
        assert ingress_vlan(port, None) == 99
        assert ingress_vlan(port, 20) is None

    def test_egress_tags_only_non_native_vlans_on_trunks(self) -> None:
        untagged = frame(MAC_A, MAC_B)
        port = trunk("t1", native_vlan=1)
        assert egress_frame(port, 1, untagged) == untagged
        assert parse_frame(egress_frame(port, 10, untagged) or b"").vlan_tag == 10

    def test_access_egress_only_in_its_vlan(self) -> None:
        port = access("p1", vlan=10)
        assert egress_frame(port, 10, b"x" * 14) == b"x" * 14
        assert egress_frame(port, 20, b"x" * 14) is None

    def test_vlan_list_parsing_and_formatting(self) -> None:
        assert parse_vlan_list("1,10,20-22") == frozenset({1, 10, 20, 21, 22})
        assert parse_vlan_list("all") is None
        assert format_vlan_list({1, 2, 3, 10, 20, 21}) == "1-3,10,20-21"
        with pytest.raises(ValueError):
            parse_vlan_list("5000")

    def test_vlan_database(self) -> None:
        db = VlanDatabase({10: "USERS"})
        db.add(20)
        assert db.items() == [(1, "default"), (10, "USERS"), (20, "VLAN0020")]
        with pytest.raises(ValueError):
            db.remove(1)
        db.remove(20)
        assert not db.exists(20)
