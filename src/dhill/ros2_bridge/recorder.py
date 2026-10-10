"""Telemetry recorder: samples robot temperatures and power on a fixed grid and writes
the CSV that ``dhill calibrate`` reads.

The recording logic (``TelemetryRecorder``) has no ROS dependency and is unit
tested. ``run_node`` wires it to ROS 2 topics and imports ``rclpy`` only when
called, so the package installs and tests without ROS.

Default topics (override with parameters): sensor_msgs/Temperature on
``/dhill/t_shell``, ``/dhill/t_interior``, ``/dhill/t_battery``, ``/dhill/t_compute``
and std_msgs/Float32 power on ``/dhill/p_compute_w``, ``/dhill/p_lidar_w``,
``/dhill/p_comms_w``, ``/dhill/p_drive_mech_w``, ``/dhill/p_payload_w``.
"""

from __future__ import annotations

import csv
import math
import time
from pathlib import Path

TEMP_FIELDS = ("t_shell_c", "t_interior_c", "t_battery_c", "t_compute_c")
POWER_FIELDS = ("p_compute_w", "p_lidar_w", "p_comms_w", "p_drive_mech_w", "p_payload_w")


class TelemetryRecorder:
    """Latest-value sampler. ``update`` stores values; ``sample`` appends a row."""

    def __init__(self, path: str | Path, dt_s: float = 300.0, max_age_s: float | None = None):
        self.path = Path(path)
        self.dt_s = dt_s
        self.max_age_s = max_age_s if max_age_s is not None else 3.0 * dt_s
        self._latest: dict[str, tuple[float, float]] = {}
        self.rows = 0
        self._fh = open(self.path, "w", newline="", encoding="utf-8")  # noqa: SIM115
        self._w = csv.writer(self._fh)
        self._w.writerow(["time_utc", *POWER_FIELDS, *TEMP_FIELDS])

    def update(self, name: str, value: float, t: float | None = None) -> None:
        if name not in POWER_FIELDS + TEMP_FIELDS:
            raise KeyError(name)
        self._latest[name] = (float(value), time.time() if t is None else t)

    def _get(self, name: str, now: float) -> float:
        v = self._latest.get(name)
        if v is None or now - v[1] > self.max_age_s or not math.isfinite(v[0]):
            return math.nan
        return v[0]

    def sample(self, now: float | None = None) -> bool:
        """Append a row. Rows lacking any power channel are skipped (loads must be known)."""
        now = time.time() if now is None else now
        powers = [self._get(n, now) for n in POWER_FIELDS]
        if any(math.isnan(p) for p in powers):
            return False
        temps = [self._get(n, now) for n in TEMP_FIELDS]
        stamp = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(now))
        self._w.writerow(
            [
                stamp,
                *[f"{p:.3f}" for p in powers],
                *["" if math.isnan(t) else f"{t:.3f}" for t in temps],
            ]
        )
        self._fh.flush()
        self.rows += 1
        return True

    def close(self) -> None:
        self._fh.close()


def run_node(
    out: str = "telemetry.csv", dt_s: float = 300.0
) -> None:  # pragma: no cover - needs ROS 2
    import rclpy
    from rclpy.node import Node
    from sensor_msgs.msg import Temperature
    from std_msgs.msg import Float32

    rclpy.init()
    node = Node("dhill_recorder")
    rec = TelemetryRecorder(out, dt_s)
    for f in TEMP_FIELDS:
        node.create_subscription(
            Temperature, f"/dhill/{f[:-2]}", lambda m, f=f: rec.update(f, m.temperature), 10
        )
    for f in POWER_FIELDS:
        node.create_subscription(Float32, f"/dhill/{f}", lambda m, f=f: rec.update(f, m.data), 10)
    node.create_timer(dt_s, rec.sample)
    try:
        rclpy.spin(node)
    finally:
        rec.close()
        node.destroy_node()
        rclpy.shutdown()
