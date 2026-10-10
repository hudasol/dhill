from __future__ import annotations

import numpy as np

from dhill.calibrate import load_telemetry_csv
from dhill.ros2_bridge.recorder import POWER_FIELDS, TEMP_FIELDS, TelemetryRecorder


def test_recorder_writes_calibration_compatible_csv(tmp_path):
    rec = TelemetryRecorder(tmp_path / "t.csv", dt_s=300.0)
    t0 = 1_785_000_000.0
    for i in range(12):
        now = t0 + 300 * i
        for n in POWER_FIELDS:
            rec.update(n, 50.0 + i, now)
        for n in TEMP_FIELDS:
            rec.update(n, 30.0 + 0.5 * i, now)
        assert rec.sample(now)
    rec.close()
    tel = load_telemetry_csv(tmp_path / "t.csv")
    assert tel.n == 12 and tel.dt_s == 300.0
    assert np.isclose(tel.temps_c["t_battery_c"][-1], 35.5)


def test_stale_and_missing_channels(tmp_path):
    rec = TelemetryRecorder(tmp_path / "t.csv", dt_s=60.0)
    now = 1_785_000_000.0
    for n in POWER_FIELDS[:-1]:
        rec.update(n, 1.0, now)
    assert not rec.sample(now)  # one power channel missing: row skipped
    rec.update(POWER_FIELDS[-1], 1.0, now)
    rec.update("t_shell_c", 40.0, now - 10_000)  # stale temperature becomes blank
    assert rec.sample(now)
    rec.close()
    lines = (tmp_path / "t.csv").read_text().splitlines()
    assert len(lines) == 2 and lines[1].endswith(",,,,")
