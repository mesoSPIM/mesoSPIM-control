"""Run the reviewer-facing Remote Control test profiles.

This runner never starts or stops mesoSPIM, MCP, or TCP. Live profiles require the operator to
start exactly one transport in the GUI and to provide the safety environment variables documented
in ``docs/source/remote_control/testing.md``.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys


TESTS = Path(__file__).resolve().parent
REPOSITORY = TESTS.parents[2]


def _run_pytest(paths, environment=None, show_output=False):
    command = [sys.executable, "-m", "pytest", *map(str, paths), "--strict-markers", "-q"]
    if show_output:
        command.append("-s")
    return subprocess.call(command, cwd=REPOSITORY, env=environment)


def _offline():
    paths = [
        TESTS / "test_commands.py",
        TESTS / "test_busy_gate.py",
        TESTS / "test_transport_matrix.py",
        TESTS / "test_transport_security.py",
        TESTS / "test_gui.py",
    ]
    return _run_pytest(paths)


def _pyqt():
    for script in (TESTS / "test_real_pyqt_smoke.py", TESTS / "test_real_pyqt_transport_smoke.py"):
        result = subprocess.call([sys.executable, str(script)], cwd=REPOSITORY, env=os.environ.copy())
        if result:
            return result
    return 0


def _live(transport):
    environment = os.environ.copy()
    environment.pop("PYTEST_ADDOPTS", None)
    environment["MESOSPIM_LIVE_DEMO_TRANSPORT"] = transport
    environment["MESOSPIM_LIVE_ADVERSARIAL_TRANSPORT"] = transport
    movement_test = {
        "mcp": "test_live_mcp_x_move_changes_position_and_restores_it",
        "tcp": "test_live_tcp_x_move_changes_position_and_restores_it",
    }[transport]
    valid = [
        f"{TESTS / 'live' / 'test_valid.py'}::{movement_test}",
        TESTS / "live" / "test_all_commands.py",
    ]
    result = _run_pytest(valid, environment=environment, show_output=True)
    if result:
        return result
    return _run_pytest(
        [TESTS / "live" / "test_adversarial.py"],
        environment=environment,
        show_output=True,
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run a Remote Control test profile")
    parser.add_argument("profile", choices=("offline", "pyqt", "live"))
    parser.add_argument("transport", nargs="?", choices=("mcp", "tcp"))
    arguments = parser.parse_args(argv)

    if arguments.profile == "live" and arguments.transport is None:
        parser.error("the live profile requires mcp or tcp")
    if arguments.profile != "live" and arguments.transport is not None:
        parser.error("a transport is valid only for the live profile")

    if arguments.profile == "offline":
        return _offline()
    if arguments.profile == "pyqt":
        return _pyqt()
    return _live(arguments.transport)


if __name__ == "__main__":
    raise SystemExit(main())
