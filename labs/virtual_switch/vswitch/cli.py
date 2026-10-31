"""IOS-flavoured interactive CLI. Commands can be abbreviated (``sh mac add``)."""

from __future__ import annotations

import cmd
from collections.abc import Sequence
from typing import IO

from .actions import SwitchActions
from .mac import to_cisco

SHOW_TOPICS = (
    "mac",
    "interfaces",
    "vlan",
    "spanning-tree",
    "port-security",
    "monitor",
    "storm-control",
)
CLEAR_TOPICS = ("mac", "counters")
NO_TOPICS = ("shutdown", "vlan", "mac")
SWITCHPORT_TOPICS = ("access", "mode", "trunk")
TRUNK_TOPICS = ("allowed", "native")
PREFERRED_COMMANDS = ("show",)  # like IOS, "sh" means show even though shutdown also matches
EOF_COMMAND = "EOF"


def match_keyword(token: str, choices: Sequence[str], preferred: Sequence[str] = ()) -> str:
    """Resolve an abbreviated keyword against ``choices``.

    A unique prefix wins; on ambiguity a keyword listed in ``preferred`` wins.
    """
    token = token.lower()
    if token in choices:
        return token
    hits = [choice for choice in choices if choice.startswith(token)]
    favourites = [hit for hit in hits if hit in preferred]
    if len(hits) == 1 or len(favourites) == 1:
        return (favourites or hits)[0]
    if not hits:
        raise ValueError(f"invalid input {token!r}, expected one of: {', '.join(choices)}")
    raise ValueError(f"ambiguous command {token!r}: {', '.join(hits)}")


def render_table(headers: Sequence[str], rows: Sequence[Sequence[object]]) -> str:
    cells = [[str(c) for c in headers]] + [[str(c) for c in row] for row in rows]
    widths = [max(len(row[i]) for row in cells) for i in range(len(headers))]
    lines = [
        "  ".join(cell.ljust(width) for cell, width in zip(row, widths, strict=True)).rstrip()
        for row in cells
    ]
    lines.insert(1, "  ".join("-" * w for w in widths))
    return "\n".join(lines)


def _int(token: str, what: str) -> int:
    try:
        return int(token)
    except ValueError:
        raise ValueError(f"{what} must be a number, got {token!r}") from None


def _require(tokens: Sequence[str], count: int, usage: str) -> None:
    if len(tokens) < count:
        raise ValueError(f"incomplete command, usage: {usage}")


class SwitchCli(cmd.Cmd):
    intro = "Virtual switch CLI. Type 'help' for commands, 'exit' to quit."

    def __init__(self, actions: SwitchActions, stdout: IO[str] | None = None) -> None:
        super().__init__(stdout=stdout)
        self.actions = actions
        self.prompt = f"{actions.hostname}# "

    # ------------------------------------------------------------ plumbing

    def onecmd(self, line: str) -> bool:
        try:
            return super().onecmd(self._expand(line))
        except ValueError as exc:
            self._write(f"% {exc}")
            return False

    def _expand(self, line: str) -> str:
        head, _, rest = line.strip().partition(" ")
        if not head or head == EOF_COMMAND or head.startswith("?"):
            return line
        commands = sorted(
            name[3:] for name in self.get_names() if name.startswith("do_") and name != "do_EOF"
        )
        return f"{match_keyword(head, commands, PREFERRED_COMMANDS)} {rest}"

    def emptyline(self) -> bool:
        return False  # do not repeat the previous command like cmd.Cmd does by default

    def _write(self, text: str) -> None:
        self.stdout.write(text + "\n")

    # --------------------------------------------------------------- show

    def do_show(self, arg: str) -> None:
        """show mac address-table [vlan <id> | interface <port>]
        show interfaces [status | counters | trunk]
        show vlan [brief]
        show spanning-tree
        show port-security
        show monitor
        show storm-control"""
        tokens = arg.split()
        _require(tokens, 1, "show <" + "|".join(SHOW_TOPICS) + ">")
        topic = match_keyword(tokens[0], SHOW_TOPICS)
        getattr(self, "_show_" + topic.replace("-", "_"))(tokens[1:])

    def _show_mac(self, args: list[str]) -> None:
        if args and "address-table".startswith(args[0].lower()):
            args = args[1:]
        vlan, port = None, None
        if args:
            _require(args, 2, "show mac address-table [vlan <id> | interface <port>]")
            if match_keyword(args[0], ("vlan", "interface")) == "vlan":
                vlan = _int(args[1], "VLAN")
            else:
                port = args[1]
        views = self.actions.mac_address_table(vlan=vlan, port=port)
        rows = [
            (
                v.entry.vlan,
                to_cisco(v.entry.mac),
                "STATIC" if v.entry.static else "DYNAMIC",
                v.entry.port,
                "-" if v.entry.static else f"{v.age:.0f}s",
            )
            for v in views
        ]
        self._write("          Mac Address Table\n")
        self._write(render_table(("Vlan", "Mac Address", "Type", "Port", "Age"), rows))
        self._write(f"\nTotal Mac Addresses: {len(rows)}")

    def _show_interfaces(self, args: list[str]) -> None:
        view = match_keyword(args[0], ("status", "counters", "trunk")) if args else "status"
        rows: list[tuple[object, ...]]
        if view == "trunk":
            rows = [(t.name, t.native_vlan, t.allowed_vlans) for t in self.actions.trunks()]
            self._write(render_table(("Port", "Native vlan", "Vlans allowed"), rows))
            return
        interfaces = self.actions.interfaces()
        if view == "counters":
            rows = [
                (
                    i.name,
                    i.counters.rx_frames,
                    i.counters.rx_bytes,
                    i.counters.rx_broadcast,
                    i.counters.rx_multicast,
                    i.counters.tx_frames,
                    i.counters.tx_bytes,
                    i.counters.dropped,
                )
                for i in interfaces
            ]
            headers = (
                "Port",
                "InFrames",
                "InOctets",
                "InBcast",
                "InMcast",
                "OutFrames",
                "OutOctets",
                "Drops",
            )
            self._write(render_table(headers, rows))
            return
        rows = [
            (
                i.name,
                i.description,
                f"{i.status} ({i.err_reason})" if i.err_reason else i.status,
                i.vlan,
                i.mode,
                i.interface,
            )
            for i in interfaces
        ]
        self._write(render_table(("Port", "Name", "Status", "Vlan", "Mode", "Interface"), rows))

    def _show_vlan(self, args: list[str]) -> None:
        rows = [(v.vlan, v.name, "active", ", ".join(v.ports)) for v in self.actions.vlans()]
        self._write(render_table(("VLAN", "Name", "Status", "Ports"), rows))

    def _show_spanning_tree(self, args: list[str]) -> None:
        stp = self.actions.spanning_tree()
        if not stp.enabled or stp.timers is None:
            self._write("Spanning tree is disabled")
            return
        self._write("Spanning tree enabled protocol ieee")
        self._write(f"  Root ID    {stp.root_id}")
        if stp.is_root:
            self._write("             This bridge is the root")
        else:
            self._write(f"             Cost {stp.root_cost}, Port {stp.root_port}")
        self._write(f"  Bridge ID  {stp.bridge_id}")
        timers = stp.timers
        self._write(
            f"  Hello Time {timers.hello_time:g}s  Max Age {timers.max_age:g}s"
            f"  Forward Delay {timers.forward_delay:g}s\n"
        )
        rows = [
            (p.name, p.role, p.state, p.cost, f"{p.port_id >> 8}.{p.port_id & 0xFF}")
            for p in stp.ports
        ]
        self._write(render_table(("Interface", "Role", "State", "Cost", "Prio.Nbr"), rows))

    def _show_port_security(self, args: list[str]) -> None:
        rows = [
            (
                s.port,
                s.max_macs,
                s.current,
                s.violations,
                s.action,
                to_cisco(s.last_violator) if s.last_violator else "-",
            )
            for s in self.actions.port_security()
        ]
        headers = ("Port", "MaxSecureAddr", "CurrentAddr", "Violations", "Action", "LastSource")
        self._write(render_table(headers, rows))

    def _show_monitor(self, args: list[str]) -> None:
        rows = [
            (s.session_id, ", ".join(sorted(s.sources)), s.direction.value, s.destination)
            for s in self.actions.span_sessions()
        ]
        self._write(render_table(("Session", "Sources", "Direction", "Destination"), rows))

    def _show_storm_control(self, args: list[str]) -> None:
        rows = [(s.port, s.limit_pps, s.suppressed) for s in self.actions.storm_control()]
        self._write(render_table(("Port", "Limit (pps)", "Suppressed"), rows))

    # ------------------------------------------------------------ configure

    def do_clear(self, arg: str) -> None:
        """clear mac address-table
        clear counters"""
        tokens = arg.split()
        _require(tokens, 1, "clear <mac address-table | counters>")
        if match_keyword(tokens[0], CLEAR_TOPICS) == "mac":
            self._write(f"Cleared {self.actions.clear_mac_table()} dynamic entries")
        else:
            self.actions.clear_counters()
            self._write("Counters cleared")

    def do_shutdown(self, arg: str) -> None:
        """shutdown <port>   administratively disable a port"""
        tokens = arg.split()
        _require(tokens, 1, "shutdown <port>")
        self.actions.shutdown(tokens[0])

    def do_no(self, arg: str) -> None:
        """no shutdown <port>               enable a port (also recovers err-disabled)
        no vlan <id>                     delete a VLAN
        no mac static <mac> vlan <id>    remove a static MAC entry"""
        tokens = arg.split()
        _require(tokens, 2, "no <shutdown|vlan|mac> ...")
        topic = match_keyword(tokens[0], NO_TOPICS)
        if topic == "shutdown":
            self.actions.no_shutdown(tokens[1])
        elif topic == "vlan":
            self.actions.delete_vlan(_int(tokens[1], "VLAN"))
        else:
            _require(tokens, 5, "no mac static <mac> vlan <id>")
            self.actions.remove_static_mac(tokens[2], _int(tokens[4], "VLAN"))

    def do_vlan(self, arg: str) -> None:
        """vlan <id> [name]   create a VLAN or rename it"""
        tokens = arg.split()
        _require(tokens, 1, "vlan <id> [name]")
        self.actions.create_vlan(_int(tokens[0], "VLAN"), tokens[1] if len(tokens) > 1 else None)

    def do_switchport(self, arg: str) -> None:
        """switchport <port> mode <access|trunk>
        switchport <port> access vlan <id>
        switchport <port> trunk allowed vlan <list|all>   e.g. 1,10,20-30
        switchport <port> trunk native vlan <id>"""
        tokens = arg.split()
        _require(tokens, 3, "switchport <port> <mode|access|trunk> ...")
        port, topic = tokens[0], match_keyword(tokens[1], SWITCHPORT_TOPICS)
        if topic == "mode":
            self.actions.set_mode(port, match_keyword(tokens[2], ("access", "trunk")))
            return
        if topic == "access":
            _require(tokens, 4, "switchport <port> access vlan <id>")
            self.actions.set_access_vlan(port, _int(tokens[3], "VLAN"))
            return
        _require(tokens, 5, "switchport <port> trunk <allowed|native> vlan <value>")
        if match_keyword(tokens[2], TRUNK_TOPICS) == "allowed":
            self.actions.set_allowed_vlans(port, tokens[4])
        else:
            self.actions.set_native_vlan(port, _int(tokens[4], "VLAN"))

    def do_mac(self, arg: str) -> None:
        """mac static <mac> vlan <id> interface <port>   add a static MAC entry"""
        tokens = arg.split()
        usage = "mac static <mac> vlan <id> interface <port>"
        _require(tokens, 6, usage)
        match_keyword(tokens[0], ("static",))
        self.actions.add_static_mac(tokens[1], _int(tokens[3], "VLAN"), tokens[5])

    # ----------------------------------------------------------------- exit

    def do_exit(self, arg: str) -> bool:
        """exit   stop the switch and leave"""
        return True

    def do_EOF(self, arg: str) -> bool:  # noqa: N802 - name required by cmd.Cmd for Ctrl+D
        self._write("")
        return True
