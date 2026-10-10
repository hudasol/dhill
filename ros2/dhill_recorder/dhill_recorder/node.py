"""Entry point: requires the ``dhill`` Python package in the same environment."""

import sys

from dhill.ros2_bridge.recorder import run_node


def main() -> None:
    out = sys.argv[1] if len(sys.argv) > 1 else "telemetry.csv"
    run_node(out)
