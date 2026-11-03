"""Adapter from Dhill decisions to Nav2 speed limits and park requests.

The mapping logic (``decision_to_command``, ``CommandFilter``, ``DecisionClient``) has no ROS dependency and
is unit tested. ``run_node`` wires it to Nav2 and imports ``rclpy`` only when called. It has **not** been run
against a live Nav2 stack in this repository (there is no ROS installation in CI); treat it as an integration
starting point and test it in simulation before any robot.

Behaviour
---------
* GO: no speed limit (``run``).
* DERATE: a speed limit as a percentage of the robot's maximum speed, from the scale Dhill found.
* PARK: a park request, published on ``/dhill/park_request``. Nav2 itself is not asked to stop with a zero
  limit, because a limit of zero may mean "no limit" to a Nav2 controller; confirm this for the installed
  Nav2 version.
* If the Dhill service cannot be reached for longer than ``stale_after_s`` the adapter fails safe to a park
  request, so a lost link never looks like a GO.

Dhill never replaces the robot's own hardware thermal protection.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Literal

import httpx

Kind = Literal["run", "limit", "park"]


@dataclass(frozen=True)
class NavCommand:
    kind: Kind
    speed_limit_percent: float | None  # set only for "limit"
    reason: str
    evidence_level: str = "L0"
    fail_safe: bool = False


def decision_to_command(
    action: str,
    scale: float,
    evidence_level: str = "L0",
    min_percent: float = 10.0,
    reason: str = "",
) -> NavCommand:
    """Map a Dhill decision to a Nav2 command."""
    if action == "GO":
        return NavCommand("run", None, reason or "GO", evidence_level)
    if action == "DERATE":
        pct = max(min_percent, min(99.0, round(scale * 100.0, 1)))
        return NavCommand("limit", pct, reason or f"DERATE at scale {scale:.2f}", evidence_level)
    if action == "PARK":
        return NavCommand("park", None, reason or "PARK", evidence_level)
    raise ValueError(f"unknown action: {action}")


class CommandFilter:
    """Suppress chatter: pass a command on only when it differs enough from the last one published."""

    def __init__(self, min_change_percent: float = 5.0):
        self.min_change = min_change_percent
        self.last: NavCommand | None = None

    def update(self, cmd: NavCommand) -> NavCommand | None:
        prev = self.last
        changed = (
            prev is None
            or prev.kind != cmd.kind
            or prev.fail_safe != cmd.fail_safe
            or (
                cmd.kind == "limit"
                and abs((cmd.speed_limit_percent or 0.0) - (prev.speed_limit_percent or 0.0))
                >= self.min_change
            )
        )
        if changed:
            self.last = cmd
            return cmd
        return None


class DecisionClient:
    """Asks a Dhill REST service for the decision at the current time, with a stale data rule."""

    def __init__(
        self,
        base_url: str,
        profile: str,
        site: str,
        api_key: str | None = None,
        stale_after_s: float = 1800.0,
        duration_h: float = 1.0,
        client: httpx.Client | None = None,
        clock=time.monotonic,
    ):
        self.url = base_url.rstrip("/") + "/v1/envelope"
        self.body = {
            "profile": profile,
            "site": site,
            "source": "live",
            "duration_h": duration_h,
            "samples": 64,
        }
        self.headers = {"X-API-Key": api_key} if api_key else {}
        self.stale_after_s = stale_after_s
        self._client = client or httpx.Client(timeout=20.0)
        self._clock = clock
        self._last_ok: float | None = None
        self.last_error: str | None = None

    def current(self, at_utc: str | None = None) -> NavCommand:
        body = dict(self.body)
        if at_utc:
            body["at"] = at_utc
        try:
            r = self._client.post(self.url, json=body, headers=self.headers)
            r.raise_for_status()
            d = r.json()
            cmd = decision_to_command(
                d["action"],
                d["scale"],
                d.get("evidence_level", "L0"),
                reason="; ".join(d.get("reasons", []))[:200],
            )
            self._last_ok = self._clock()
            self.last_error = None
            return cmd
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            self.last_error = str(exc)[:200]
            now = self._clock()
            if self._last_ok is None or now - self._last_ok > self.stale_after_s:
                return NavCommand(
                    "park", None, f"no fresh decision: {self.last_error}", fail_safe=True
                )
            raise


def run_node() -> None:  # pragma: no cover - needs ROS 2 and Nav2
    import rclpy
    from nav2_msgs.msg import SpeedLimit
    from rclpy.node import Node
    from std_msgs.msg import Bool

    rclpy.init()
    node = Node("dhill_nav2_adapter")
    p = node.declare_parameter
    base = p("dhill_url", "http://127.0.0.1:8080").value
    profile = p("profile", "ugv_medium_inspection").value
    site = p("site", "abu_dhabi").value
    key = p("api_key", "").value or None
    period = float(p("period_s", 300.0).value)
    client = DecisionClient(base, profile, site, key)
    filt = CommandFilter()
    limit_pub = node.create_publisher(SpeedLimit, "speed_limit", 10)
    park_pub = node.create_publisher(Bool, "dhill/park_request", 10)

    def tick() -> None:
        try:
            cmd = client.current()
        except Exception as exc:
            node.get_logger().warn(f"keeping the last command: {exc}")
            return
        out = filt.update(cmd)
        if out is None:
            return
        node.get_logger().info(f"{out.kind} {out.speed_limit_percent} {out.reason}")
        msg = SpeedLimit()
        msg.percentage = True
        msg.speed_limit = out.speed_limit_percent if out.kind == "limit" else 0.0
        limit_pub.publish(msg)
        park = Bool()
        park.data = out.kind == "park"
        park_pub.publish(park)

    node.create_timer(period, tick)
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
