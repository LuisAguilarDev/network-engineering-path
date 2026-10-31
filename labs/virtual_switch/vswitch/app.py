"""Composition root: wires configuration, adapters, engine and CLI together."""

from __future__ import annotations

import argparse
import logging
import sys
import threading
from collections.abc import Callable, Sequence
from pathlib import Path

from .actions import SwitchActions
from .adapters.scapy_io import ScapyFrameIO
from .adapters.system_clock import SystemClock
from .cli import SwitchCli
from .config_loader import ConfigError, load_config
from .switch import VirtualSwitch

logger = logging.getLogger(__name__)

TICK_INTERVAL_SECONDS = 1.0
EXIT_OK = 0
EXIT_RUNTIME_ERROR = 1
EXIT_CONFIG_ERROR = 2
LOG_FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"


class Ticker:
    """Runs ``callback`` every ``interval`` seconds on a daemon thread."""

    def __init__(self, callback: Callable[[], None], interval: float) -> None:
        self._callback = callback
        self._interval = interval
        self._stopped = threading.Event()
        self._thread = threading.Thread(target=self._run, name="vswitch-ticker", daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stopped.set()
        self._thread.join(timeout=self._interval * 2)

    def _run(self) -> None:
        while not self._stopped.wait(self._interval):
            try:
                self._callback()
            except Exception:  # a failing tick must not kill the timer thread
                logger.exception("periodic task failed")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="vswitch", description="Virtual L2 switch built on scapy")
    parser.add_argument("-c", "--config", type=Path, required=True, help="TOML configuration file")
    parser.add_argument("--no-cli", action="store_true", help="run headless until Ctrl+C")
    parser.add_argument("--log-level", default="WARNING", help="DEBUG, INFO, WARNING, ERROR")
    parser.add_argument("--log-file", type=Path, help="write logs to a file instead of stderr")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=args.log_level.upper(),
        format=LOG_FORMAT,
        filename=args.log_file,
    )
    try:
        config = load_config(args.config)
    except (OSError, ConfigError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_CONFIG_ERROR

    switch = VirtualSwitch(
        config, ScapyFrameIO({p.name: p.interface for p in config.ports}), SystemClock()
    )
    try:
        switch.start()
    except PermissionError:
        print("error: raw sockets need root, run with sudo", file=sys.stderr)
        return EXIT_RUNTIME_ERROR
    except OSError as exc:
        print(f"error: {exc} (did you run 'scripts/topology.py up'?)", file=sys.stderr)
        return EXIT_RUNTIME_ERROR

    ticker = Ticker(switch.tick, TICK_INTERVAL_SECONDS)
    ticker.start()
    try:
        if args.no_cli:
            print(f"{config.name} running headless, press Ctrl+C to stop")
            threading.Event().wait()
        else:
            SwitchCli(SwitchActions(switch)).cmdloop()
    except KeyboardInterrupt:
        pass
    finally:
        ticker.stop()
        switch.stop()
    return EXIT_OK
