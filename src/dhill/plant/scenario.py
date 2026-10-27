"""Scenario builders for the plant: minute scale weather, moving shade, patrol duty, dust fronts.

SYNTHETIC. The hourly weather is taken from a record (recorded or synthetic); everything finer than an
hour is generated here from stated statistical models, because hourly records cannot show it.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.signal import lfilter

from .model import PlantDrive, PlantForcing, PlantParams, erbs_split, solar_geometry


@dataclass
class PlantWeather:
    """Hourly (or finer) weather for one site. No dependence on the engine's Weather class."""

    times_utc: np.ndarray
    t_air_c: np.ndarray
    dew_c: np.ndarray
    wind10: np.ndarray
    ghi: np.ndarray
    pm10: np.ndarray
    precip_mm_h: np.ndarray
    lat: float
    lon: float
    altitude_m: float = 0.0
    label: str = ""

    def seconds(self) -> np.ndarray:
        return (self.times_utc - self.times_utc[0]).astype("timedelta64[s]").astype(float)


@dataclass
class DustEvent:
    """A dust front: wind gust, temperature drop, particulate spike and beam attenuation."""

    onset_s: float  # seconds after the start of the simulated window
    duration_s: float = 5400.0
    peak_pm10: float = 2500.0
    wind_boost: float = 9.0
    temp_drop_k: float = 5.0
    beam_cut_per_ugm3: float = 0.0009


@dataclass
class Micro:
    """Sub hourly variability, as relative or absolute standard deviations of AR(1) processes."""

    t_sigma_k: float = 0.4
    t_tau_s: float = 600.0
    gust_sigma: float = 0.35
    gust_tau_s: float = 180.0
    cloud_sigma: float = 0.04
    cloud_tau_s: float = 900.0
    pm_sigma: float = 0.30
    pm_tau_s: float = 1200.0
    event: DustEvent | None = None
    enabled: bool = True


def _ar1(rng: np.random.Generator, shape: tuple[int, int], dt: float, tau: float) -> np.ndarray:
    """Unit variance AR(1) noise, stationary from the first sample."""
    phi = float(np.exp(-dt / tau))
    eps = rng.standard_normal(shape)
    x0 = rng.standard_normal((shape[0], 1))
    out, _ = lfilter([np.sqrt(1.0 - phi**2)], [1.0, -phi], eps, axis=1, zi=phi * x0)
    return out


def build_forcing(
    wx: PlantWeather,
    start_s: np.ndarray,
    steps: int,
    dt: float,
    rng: np.random.Generator,
    micro: Micro | None = None,
) -> PlantForcing:
    """Fine grid forcing (B, steps) starting ``start_s`` seconds after the first record time."""
    micro = micro or Micro(enabled=False)
    b = start_s.shape[0]
    rel = np.arange(steps) * dt
    ts = start_s[:, None] + rel[None, :]
    x = wx.seconds()

    def itp(y):
        return np.interp(ts, x, np.asarray(y, dtype=float))

    t_air = itp(wx.t_air_c)
    dew = itp(wx.dew_c)
    wind = itp(wx.wind10)
    ghi = itp(wx.ghi)
    pm = itp(wx.pm10)
    rain = itp(wx.precip_mm_h)
    if micro.enabled:
        t_air = t_air + micro.t_sigma_k * _ar1(rng, (b, steps), dt, micro.t_tau_s)
        g = _ar1(rng, (b, steps), dt, micro.gust_tau_s)
        wind = wind * np.exp(micro.gust_sigma * g - 0.5 * micro.gust_sigma**2)
        c = _ar1(rng, (b, steps), dt, micro.cloud_tau_s)
        ghi = np.maximum(ghi * (1.0 + micro.cloud_sigma * c), 0.0)
        m = _ar1(rng, (b, steps), dt, micro.pm_tau_s)
        pm = pm * np.exp(micro.pm_sigma * m - 0.5 * micro.pm_sigma**2)
    dew = np.minimum(dew, t_air - 0.1)

    abs_times = wx.times_utc[0] + ts.astype("timedelta64[s]")
    el, az, doy = solar_geometry(abs_times, wx.lat, wx.lon)
    sin_el = np.sin(np.maximum(el, 0.0))
    cos_el = np.cos(np.maximum(el, 0.0))
    dni, dhi = erbs_split(ghi, np.sin(el), doy)

    ev = micro.event if micro.enabled else None
    if ev is not None:
        dtau = rel[None, :] - np.full((b, 1), ev.onset_s)
        on = dtau >= 0.0
        ramp = np.clip(dtau / 600.0, 0.0, 1.0)
        decay = np.exp(-np.maximum(dtau - 600.0, 0.0) / (ev.duration_s / 3.0))
        extra_pm = np.where(on, ev.peak_pm10 * ramp * decay, 0.0)
        wind = wind + np.where(on, ev.wind_boost * np.exp(-np.maximum(dtau, 0.0) / 900.0), 0.0)
        t_air = t_air - np.where(
            on, ev.temp_drop_k * np.exp(-np.maximum(dtau, 0.0) / ev.duration_s), 0.0
        )
        pm = pm + extra_pm
        lost = dni * (1.0 - np.exp(-ev.beam_cut_per_ugm3 * extra_pm))
        dni = dni - lost
        dhi = dhi + 0.35 * lost * sin_el

    hour = (abs_times - abs_times.astype("datetime64[D]")).astype("timedelta64[s]").astype(
        float
    ) / 3600.0
    solar_hour = (hour + wx.lon / 15.0) % 24.0
    return PlantForcing(
        dt_s=dt,
        t_air_c=t_air,
        dew_c=dew,
        wind10=np.maximum(wind, 0.0),
        dni=dni,
        dhi=dhi,
        ghi=np.maximum(dni * sin_el + dhi, 0.0),
        sin_el=sin_el,
        cos_el=cos_el,
        azimuth=az,
        pm10=np.maximum(pm, 0.0),
        rain_mm_h=np.maximum(rain, 0.0),
        solar_hour=solar_hour,
    )


# ---------------------------------------------------------------------------- shade
def _markov(rng, b, steps, dt, mean_on_s, mean_off_s, start_on_prob=0.3):
    stay_on = np.exp(-dt / mean_on_s)
    stay_off = np.exp(-dt / mean_off_s)
    state = rng.random(b) < start_on_prob
    out = np.empty((b, steps), dtype=bool)
    for k in range(steps):
        out[:, k] = state
        u = rng.random(b)
        state = np.where(state, u < stay_on, u >= stay_off)
    return out


def build_shade(forc: PlantForcing, rng: np.random.Generator, kind: str = "urban") -> np.ndarray:
    """Share of the beam blocked, (B, T). Kinds: none, open, urban, shelter."""
    b, steps = forc.t_air_c.shape
    dt = forc.dt_s
    if kind == "none":
        return np.zeros((b, steps))
    if kind == "shelter":
        return np.ones((b, steps))
    if kind == "open":
        tree = _markov(rng, b, steps, dt, 240.0, 3000.0, 0.05)
        return tree.astype(float)
    if kind != "urban":
        raise ValueError(f"unknown shade kind {kind}")
    tree = _markov(rng, b, steps, dt, 420.0, 1200.0, 0.2)
    row = _markov(rng, b, steps, dt, 1200.0, 900.0, 0.4)
    a0 = rng.uniform(0.0, 2.0 * np.pi, size=(b, 1))
    width = np.radians(rng.uniform(40.0, 110.0, size=(b, 1)))
    cut = np.radians(rng.uniform(20.0, 50.0, size=(b, 1)))
    rel_az = (forc.azimuth - a0) % (2.0 * np.pi)
    in_window = rel_az < width
    low_sun = np.arcsin(np.clip(forc.sin_el, 0.0, 1.0)) < cut
    return np.maximum(tree, row & in_window & low_sun).astype(float)


# ---------------------------------------------------------------------------- duty
def build_mission(
    p: PlantParams,
    scale: np.ndarray,
    spin_steps: int,
    steps: int,
    dt: float,
    rng: np.random.Generator,
    v_nom: float = 1.0,
    p_mech_full: float = 50.0,
    p_payload_full: float = 10.0,
    stop_share: float = 0.08,
    sand_share: float = 0.10,
) -> PlantDrive:
    """Parked for ``spin_steps`` then a patrol at ``scale`` (B,) for the rest; stops, turns and sand patches."""
    b = p.n
    scale = np.asarray(scale, dtype=float)
    # scale is (B,) for a constant patrol or (B, steps) for a schedule
    s = np.broadcast_to(scale if scale.ndim == 2 else scale[:, None], (b, steps)).copy()
    moving = np.zeros((b, steps), dtype=bool)
    moving[:, spin_steps:] = True
    stops = _markov(rng, b, steps, dt, 90.0, 90.0 * (1.0 - stop_share) / stop_share, 0.0)
    moving &= ~stops
    moving &= s > 0.0

    sand = _markov(rng, b, steps, dt, 240.0, 240.0 * (1.0 - sand_share) / sand_share, 0.0)
    load_noise = _ar1(rng, (b, steps), dt, 60.0)
    util_noise = _ar1(rng, (b, steps), dt, 120.0)
    p_mech = np.where(
        moving, p_mech_full * s * (1.0 + 0.2 * load_noise) * np.where(sand, 1.5, 1.0), 0.0
    )
    p_mech = np.clip(p_mech, 0.0, 2.0 * p_mech_full)
    util = np.clip(s * (1.0 + 0.2 * util_noise), 0.0, 1.0)
    active = (s > 0.0) & (np.arange(steps)[None, :] >= spin_steps)
    p_comp = p.p_comp_idle[:, None] + (p.p_comp_max - p.p_comp_idle)[:, None] * np.where(
        active, util, 0.0
    )
    p_lidar = np.where(moving, p.p_lidar_on[:, None], 0.0)
    p_payload = np.where(moving, p_payload_full * s, 0.0)
    p_elec = np.repeat(p.p_elec[:, None], steps, axis=1)
    speed = np.where(moving, v_nom * s * (1.0 + 0.1 * load_noise), 0.0)

    # heading: a new heading every 5 to 10 minutes, turns of 90 or 180 degrees
    heading = np.empty((b, steps))
    h = rng.uniform(0.0, 2.0 * np.pi, size=b)
    nxt = rng.uniform(300.0, 600.0, size=b)
    for k in range(steps):
        t = k * dt
        turn = t >= nxt
        if turn.any():
            h = np.where(turn, h + rng.choice([-1.0, 1.0, 2.0], size=b) * 0.5 * np.pi, h)
            nxt = np.where(turn, t + rng.uniform(300.0, 600.0, size=b), nxt)
        heading[:, k] = h % (2.0 * np.pi)
    return PlantDrive(
        p_comp=p_comp,
        p_lidar=p_lidar,
        p_elec=p_elec,
        p_mech=p_mech,
        p_payload=p_payload,
        speed=speed,
        heading=heading,
        shade_beam=np.zeros((b, steps)),
    )


def field_schedule(
    b: int,
    steps: int,
    dt: float,
    local_start_hour: float,
    rng: np.random.Generator,
    work_from_h: float = 6.0,
    work_to_h: float = 20.0,
    cycle_min: float = 60.0,
    drive_min: float = 35.0,
) -> np.ndarray:
    """Scale schedule (B, steps) of a logging day: drive 35 minutes of each hour at a varied scale, else parked."""
    out = np.zeros((b, steps))
    cyc = int(round(cycle_min * 60.0 / dt))
    drv = int(round(drive_min * 60.0 / dt))
    n_cycles = steps // cyc + 2
    levels = rng.uniform(0.5, 1.0, size=(b, n_cycles))
    for k in range(steps):
        hour = local_start_hour + k * dt / 3600.0
        if work_from_h <= hour % 24.0 < work_to_h and (k % cyc) < drv:
            out[:, k] = levels[:, k // cyc]
    return out
