"""Entry point: requires the ``dhill`` Python package in the same environment."""

from dhill.ros2_bridge.nav2_adapter import run_node


def main() -> None:
    run_node()
