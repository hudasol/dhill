"""Calibrate thermal parameters on telemetry and quantify what was identified.

Free parameters are fitted in log space with bounded least squares against
measured node temperatures. The Jacobian gives approximate confidence
intervals; parameters whose interval is wide are reported as not identified and
keep their prior uncertainty. A held-out tail of the record measures predictive
error. Calibration yields evidence level L2 at most: L3 needs an independent
field campaign.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from pydantic import BaseModel
from scipy.optimize import least_squares

from .physics.constants import c_to_k, k_to_c
from .physics.thermal import Loads, State, ThermalParams, simulate
from .profiles.registry import PARAMS
from .profiles.schema import ParamSpec, Profile
from .weather.base import Weather

NODE_COLS = {
    "t_shell_c": 0,
    "t_interior_c": 1,
    "t_battery_c": 2,
    "t_compute_c": 3,
    "t_lidar_c": 4,
    "t_motor_c": 5,
}
LOAD_COLS = ("p_compute_w", "p_lidar_w", "p_comms_w", "p_drive_mech_w", "p_payload_w")

DEFAULT_FREE = (
    "surface.alpha_clean",
    "coupling.ua_shell_interior_w_k",
    "shell.heat_capacity_j_k",
    "interior.heat_capacity_j_k",
    "coupling.ua_battery_interior_w_k",
)


@dataclass
class Telemetry:
    times_utc: np.ndarray
    loads: dict[str, np.ndarray]
    temps_c: dict[str, np.ndarray]  # NODE_COLS key -> series (NaN = missing)

    @property
    def n(self) -> int:
        return int(self.times_utc.shape[0])

    @property
    def dt_s(self) -> float:
        return float(np.median(np.diff(self.times_utc).astype("timedelta64[s]").astype(float)))


def load_telemetry_csv(path: str | Path) -> Telemetry:
    with open(path, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    if len(rows) < 10:
        raise ValueError("telemetry needs at least 10 rows")
    times = np.array([r["time_utc"] for r in rows], dtype="datetime64[s]")
    steps = np.diff(times).astype("timedelta64[s]").astype(float)
    if np.ptp(steps) > 1e-6:
        raise ValueError("telemetry must be on a uniform time grid")
    missing = [c for c in LOAD_COLS if c not in rows[0]]
    if missing:
        raise ValueError(f"telemetry missing load columns: {missing}")
    loads = {c: np.array([float(r[c]) for r in rows]) for c in LOAD_COLS}
    temps = {
        c: np.array([float(r[c]) if r.get(c, "") != "" else np.nan for r in rows])
        for c in NODE_COLS
        if c in rows[0]
    }
    if not temps:
        raise ValueError("telemetry has no temperature columns")
    return Telemetry(times, loads, temps)


def save_telemetry_csv(tel: Telemetry, path: str | Path) -> None:
    cols = ["time_utc", *LOAD_COLS, *tel.temps_c]
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        for i in range(tel.n):
            w.writerow(
                [
                    str(tel.times_utc[i]),
                    *[f"{tel.loads[c][i]:.3f}" for c in LOAD_COLS],
                    *[f"{tel.temps_c[c][i]:.3f}" for c in tel.temps_c],
                ]
            )


def _simulate(
    profile: Profile,
    weather: Weather,
    tel: Telemetry,
    lo: int,
    hi: int,
    t0_k: np.ndarray | None = None,
) -> np.ndarray:
    """Simulated node temperatures (K) for telemetry rows lo+1..hi-1, shape (hi-lo-1, 6)."""
    forcing = weather.to_forcing(tel.dt_s)
    start = int(
        round(
            float((tel.times_utc[lo] - weather.times_utc[0]).astype("timedelta64[s]").astype(float))
            / tel.dt_s
        )
    )
    p = ThermalParams.from_profile(profile)
    if t0_k is None:
        t0 = np.empty(6)
        for c, j in NODE_COLS.items():
            if c in tel.temps_c and np.isfinite(tel.temps_c[c][lo]):
                t0[j] = c_to_k(tel.temps_c[c][lo])
        fill = t0[1] if np.isfinite(t0[1]) else c_to_k(tel.temps_c[next(iter(tel.temps_c))][lo])
        for j in range(6):
            if not np.isfinite(t0[j]) or t0[j] == 0 or np.isnan(t0[j]):
                t0[j] = fill
        t0_k = t0
    st = State(t0_k[None, :].copy(), np.array([profile.operations.soc_start]), np.zeros(1))
    sl = slice(lo, hi - 1)
    ld = Loads(**{k: tel.loads[k][sl][None, :] for k in LOAD_COLS})
    res = simulate(p, forcing, ld, st, start, hi - 1 - lo)
    return res.t_k[0, 1:, :]


def _residuals(profile: Profile, weather: Weather, tel: Telemetry, lo: int, hi: int) -> np.ndarray:
    sim = _simulate(profile, weather, tel, lo, hi)
    out = []
    for c, j in NODE_COLS.items():
        if c in tel.temps_c:
            meas = c_to_k(tel.temps_c[c][lo + 1 : hi])
            d = sim[:, j] - meas
            out.append(np.where(np.isfinite(meas), d, 0.0))
    return np.concatenate(out)


class ParamFit(BaseModel):
    key: str
    prior: float
    fitted: float
    rel_ci95: float
    identified: bool


class CalibrationResult(BaseModel):
    params: list[ParamFit]
    rmse_train_k: float
    rmse_holdout_k: float
    rmse_prior_holdout_k: float
    n_train: int
    n_holdout: int
    cost: float
    success: bool


def calibrate(
    profile: Profile,
    weather: Weather,
    tel: Telemetry,
    free: tuple[str, ...] = DEFAULT_FREE,
    holdout_frac: float = 0.3,
    ci_threshold: float = 0.5,
) -> tuple[Profile, CalibrationResult]:
    """Fit ``free`` parameters; return the calibrated profile and a report."""
    n = tel.n
    split = int(n * (1.0 - holdout_frac))
    if split < 8 or n - split < 4:
        raise ValueError("record too short for a train/holdout split")
    prior = np.array([profile.value(k) for k in free])
    lo_b = np.array([PARAMS[k].lo for k in free]) / prior
    hi_b = np.array([PARAMS[k].hi for k in free]) / prior
    lb, ub = np.log(np.maximum(lo_b, 1e-3)), np.log(hi_b)

    def make(theta_log: np.ndarray) -> Profile:
        return profile.with_overrides(
            {k: float(v * np.exp(t)) for k, v, t in zip(free, prior, theta_log, strict=True)}
        )

    def fun(theta: np.ndarray) -> np.ndarray:
        return _residuals(make(theta), weather, tel, 0, split)

    x0 = np.zeros(len(free))
    sol = least_squares(fun, x0, bounds=(lb, ub), diff_step=1e-3, x_scale=0.2, max_nfev=60)
    r = sol.fun
    dof = max(1, r.size - len(free))
    s2 = float(r @ r) / dof
    jac = sol.jac
    try:
        cov = s2 * np.linalg.inv(jac.T @ jac)
        se = np.sqrt(np.maximum(np.diag(cov), 0.0))
    except np.linalg.LinAlgError:
        se = np.full(len(free), np.inf)
    fitted = prior * np.exp(sol.x)
    ci = 1.96 * se
    fits = [
        ParamFit(
            key=k,
            prior=float(p0),
            fitted=float(v),
            rel_ci95=float(c),
            identified=bool(c < ci_threshold),
        )
        for k, p0, v, c in zip(free, prior, fitted, ci, strict=True)
    ]
    cal = profile.model_copy(deep=True)
    for f in fits:
        base = cal.parameters.get(f.key)
        sigma = min(0.05, f.rel_ci95 / 1.96) if f.identified else None
        cal.parameters[f.key] = ParamSpec(
            value=f.fitted if f.identified else f.prior,
            source="calibrated" if f.identified else (base.source if base else "assumption"),
            note=(base.note if base else None),
            rel_sigma=sigma if f.identified else (base.rel_sigma if base else None),
        )
    if any(f.identified for f in fits):
        cal = cal.model_copy(
            update={
                "evidence_level": "L2",
                "calibrated_from": [*profile.calibrated_from, "telemetry"],
            }
        )

    def rmse(prof: Profile, lo: int, hi: int) -> float:
        rr = _residuals(prof, weather, tel, lo, hi)
        used = rr[rr != 0.0]
        return float(np.sqrt(np.mean(used**2))) if used.size else float("nan")

    result = CalibrationResult(
        params=fits,
        rmse_train_k=rmse(cal, 0, split),
        rmse_holdout_k=_holdout_rmse(cal, weather, tel, split),
        rmse_prior_holdout_k=_holdout_rmse(profile, weather, tel, split),
        n_train=split - 1,
        n_holdout=n - split - 1,
        cost=float(sol.cost),
        success=bool(sol.success),
    )
    return cal, result


def _holdout_rmse(profile: Profile, weather: Weather, tel: Telemetry, split: int) -> float:
    """Error on the tail, started from the measured state at the split (one-segment forecast)."""
    rr = _residuals(profile, weather, tel, split, tel.n)
    used = rr[rr != 0.0]
    return float(np.sqrt(np.mean(used**2))) if used.size else float("nan")


def synthetic_telemetry(
    true_profile: Profile,
    weather: Weather,
    start_utc: str,
    hours: float = 16.0,
    dt_s: float = 300.0,
    noise_k: float = 0.3,
    seed: int = 0,
    sensors: tuple[str, ...] = ("t_shell_c", "t_interior_c", "t_battery_c", "t_compute_c"),
) -> Telemetry:
    """Generate telemetry from a 'true' robot with a stop-start duty cycle and sensor noise."""
    rng = np.random.default_rng(seed)
    forcing = weather.to_forcing(dt_s)
    n = int(hours * 3600 / dt_s)
    t0 = np.datetime64(start_utc, "s")
    times = t0 + (np.arange(n + 1) * dt_s).astype("timedelta64[s]")
    pr = true_profile
    m = pr.modes["drive"]
    cycle = int(60 * 60 / dt_s)  # 60-minute cycle: 35 min drive at varying scale, rest otherwise
    scale = np.zeros(n)
    for i in range(n):
        ph = i % cycle
        scale[i] = (0.6 + 0.4 * np.sin(i / 7.0) ** 2) if ph < int(35 * 60 / dt_s) else 0.0
    f_min = pr.value("compute.min_power_fraction")
    loads = {
        "p_compute_w": pr.value("compute.nominal_power_w") * (f_min + (1 - f_min) * scale),
        "p_lidar_w": np.where(scale > 0, pr.value("lidar.power_w"), 0.0),
        "p_comms_w": np.full(n, pr.value("power.comms_w") + pr.value("power.standby_w")),
        "p_drive_mech_w": m.mech_w * scale,
        "p_payload_w": m.payload_w * scale,
    }
    p = ThermalParams.from_profile(pr)
    start = int(
        round(float((t0 - weather.times_utc[0]).astype("timedelta64[s]").astype(float)) / dt_s)
    )
    t_air = forcing.t_air_k[start]
    st = State(np.full((1, 6), t_air), np.array([pr.operations.soc_start]), np.zeros(1))
    res = simulate(p, forcing, Loads(**{k: v[None, :] for k, v in loads.items()}), st, start, n)
    temps = {}
    for c in sensors:
        series = k_to_c(res.t_k[0, :, NODE_COLS[c]]) + noise_k * rng.standard_normal(n + 1)
        temps[c] = series
    # drop the last row of loads so arrays align with n+1 samples (repeat last)
    loads = {k: np.append(v, v[-1]) for k, v in loads.items()}
    return Telemetry(times, loads, temps)
