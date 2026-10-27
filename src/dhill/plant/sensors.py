"""Sensor model: turn plant temperatures and loads into the telemetry a real logger would record.

SYNTHETIC. Real sensors lag the surface they sit on, carry an offset, add noise, quantise, and miss rows.
Measured loads are estimates with a scale error (drive mechanical power is inferred, not measured).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .model import AIR, BSURF, HSINK, LIDAR, MOTOR, TOP, PlantDrive, PlantTrace

# telemetry column -> plant node the sensor is fixed to
SENSOR_NODE = {
    "t_shell_c": TOP,
    "t_interior_c": AIR,
    "t_battery_c": BSURF,
    "t_compute_c": HSINK,
    "t_lidar_c": LIDAR,
    "t_motor_c": MOTOR,
}
SENSOR_LAG_S = {
    "t_shell_c": 40.0,
    "t_interior_c": 90.0,
    "t_battery_c": 120.0,
    "t_compute_c": 45.0,
    "t_lidar_c": 60.0,
    "t_motor_c": 100.0,
}


@dataclass
class SensorSpec:
    sample_s: float = 60.0
    noise_k: float = 0.15
    bias_sigma_k: float = 0.4
    quant_k: float = 0.1
    dropout_mean_rows: float = 4.0
    dropout_share: float = 0.02
    load_noise_rel: float = 0.03
    load_bias_sigma_rel: float = 0.08
    columns: tuple[str, ...] = ("t_shell_c", "t_interior_c", "t_battery_c", "t_compute_c")
    lag_scale: float = 1.0
    enabled: bool = True


@dataclass
class Record:
    """Telemetry arrays for one run; ``seconds`` counts from the first sample."""

    seconds: np.ndarray
    loads: dict[str, np.ndarray]
    temps_c: dict[str, np.ndarray]
    truth_c: dict[str, np.ndarray] = field(default_factory=dict)


def measure(
    trace: PlantTrace,
    drv: PlantDrive,
    member: int,
    rng: np.random.Generator,
    spec: SensorSpec | None = None,
    first_step: int = 0,
) -> Record:
    """Telemetry for batch member ``member`` from step ``first_step`` of the trace."""
    spec = spec or SensorSpec()
    dt = trace.dt_s
    stride = max(1, int(round(spec.sample_s / dt)))
    t_c = trace.temps_c()[member]  # (T+1, N)
    n_all = t_c.shape[0]
    idx = np.arange(first_step, n_all, stride)
    temps: dict[str, np.ndarray] = {}
    truth: dict[str, np.ndarray] = {}
    for col in spec.columns:
        x = t_c[:, SENSOR_NODE[col]]
        truth[col] = x[idx]
        if not spec.enabled:
            temps[col] = x[idx].copy()
            continue
        tau = SENSOR_LAG_S[col] * spec.lag_scale
        a = 1.0 - np.exp(-dt / tau)
        y = np.empty_like(x)
        y[0] = x[0]
        for k in range(1, n_all):
            y[k] = y[k - 1] + a * (x[k] - y[k - 1])
        meas = (
            y[idx]
            + spec.bias_sigma_k * rng.standard_normal()
            + spec.noise_k * rng.standard_normal(idx.size)
        )
        if spec.quant_k > 0:
            meas = np.round(meas / spec.quant_k) * spec.quant_k
        temps[col] = meas
    if spec.enabled and spec.dropout_share > 0:
        stay = 1.0 - 1.0 / spec.dropout_mean_rows
        enter = spec.dropout_share / (spec.dropout_mean_rows * (1.0 - spec.dropout_share))
        gap = np.zeros(idx.size, dtype=bool)
        state = False
        for i in range(1, idx.size):
            state = rng.random() < (stay if state else enter)
            gap[i] = state
        for col in temps:
            temps[col] = np.where(gap, np.nan, temps[col])

    def load(name: str, arr: np.ndarray) -> np.ndarray:
        row = arr[member, :]
        series = np.concatenate([row, row[-1:]])[idx]
        if not spec.enabled:
            return series
        bias = (
            1.0 + spec.load_bias_sigma_rel * rng.standard_normal()
            if name == "p_drive_mech_w"
            else 1.0
        )
        return np.maximum(
            series * bias * (1.0 + spec.load_noise_rel * rng.standard_normal(series.size)), 0.0
        )

    loads = {
        "p_compute_w": load("p_compute_w", drv.p_comp),
        "p_lidar_w": load("p_lidar_w", drv.p_lidar),
        "p_comms_w": load("p_comms_w", drv.p_elec),
        "p_drive_mech_w": load("p_drive_mech_w", drv.p_mech),
        "p_payload_w": load("p_payload_w", drv.p_payload),
    }
    return Record(seconds=(idx - first_step) * dt, loads=loads, temps_c=temps, truth_c=truth)
