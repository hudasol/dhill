"""Test the engine against the independent plant: structural model error on recorded weather.

The engine (``dhill.envelope``) decides from an hourly weather record and a class profile. The plant
(``dhill.plant``) is a different sixteen node robot, drawn from one of three classes, driven by the same
record plus minute scale variability. This module runs both on the same slots and reports where the
engine's prediction and decision fail. Everything here is SYNTHETIC and at evidence level L0: the plant is
a reasoned design, not a measurement. It tests robustness to structural error of the kind a richer
physical model would show, not accuracy on any real robot.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np

from .climatology import SiteRecord, pm10_hourly_median
from .envelope import EngineConfig, Envelope
from .plant.model import AIR, BCORE, DIE, LIDAR, MOTOR, PlantParams, PlantState, simulate_plant
from .plant.scenario import (
    DustEvent,
    Micro,
    PlantWeather,
    build_forcing,
    build_mission,
    build_shade,
    field_schedule,
)
from .policies import ambient_threshold, slot_starts
from .profiles.registry import COMPONENTS
from .profiles.schema import Profile
from .weather.base import Weather

COMPONENT_NODE = {
    "battery": BCORE,
    "compute_die": DIE,
    "lidar": LIDAR,
    "motor": MOTOR,
    "interior": AIR,
}
LOCAL_OFFSET_H = 4  # UAE standard time
SPIN_H = 3.0
CLASS_PROFILE = {
    "small_ugv": "ugv_medium_inspection",
    "delivery": "sidewalk_delivery_robot",
    "pv_cleaner": "pv_cleaning_robot",
}
CLASSES = tuple(CLASS_PROFILE)
SCALE_GRID = np.round(np.linspace(0.0, 1.0, 11), 2)
POLICIES = ("P1", "P2", "P3", "P4", "P5", "P6")


# ---------------------------------------------------------------------------- weather
def _fill_pm(rec: SiteRecord, sel: np.ndarray, pm_median: dict | None) -> np.ndarray:
    pm = rec.pm10_ugm3[sel].copy()
    if np.isnan(pm).any():
        med = pm_median if pm_median is not None else pm10_hourly_median(rec)
        local = rec.times_utc[sel] + np.timedelta64(LOCAL_OFFSET_H, "h")
        months = (local.astype("datetime64[M]").astype(int) % 12) + 1
        hours = local.astype("datetime64[h]").astype(int) % 24
        for i in np.where(np.isnan(pm))[0]:
            pm[i] = med.get((int(months[i]), int(hours[i])), 60.0)
    return pm


def _weather(rec: SiteRecord, sel: np.ndarray, pm_median: dict | None) -> Weather:
    return Weather(
        times_utc=rec.times_utc[sel],
        t_air_c=rec.t_air_c[sel],
        dew_c=np.minimum(rec.dew_c[sel], rec.t_air_c[sel]),
        wind10_ms=rec.wind10_ms[sel],
        pm10_ugm3=_fill_pm(rec, sel, pm_median),
        precip_mm_h=rec.precip_mm_h[sel],
        lat=rec.site.lat,
        lon=rec.site.lon,
        altitude_m=rec.site.altitude_m,
        ghi_wm2=rec.ghi_wm2[sel],
        source="open-meteo-archive",
        label=rec.site.id,
    )


def window_weather(rec: SiteRecord, day_utc: str, pm_median: dict | None = None) -> Weather:
    """Recorded weather from 20:00 UTC the evening before ``day_utc`` to 16:00 UTC of that day."""
    d = np.datetime64(day_utc, "D")
    t0 = d.astype("datetime64[s]") - np.timedelta64(4, "h")
    t1 = d.astype("datetime64[s]") + np.timedelta64(16, "h")
    sel = (rec.times_utc >= t0) & (rec.times_utc <= t1)
    if sel.sum() < 12:
        raise ValueError(f"record does not cover {day_utc}")
    return _weather(rec, sel, pm_median)


def span_weather(
    rec: SiteRecord, start_utc: str, hours: float, pm_median: dict | None = None
) -> Weather:
    """Recorded weather covering ``hours`` after ``start_utc``, with one hour of margin each side."""
    t0 = np.datetime64(start_utc, "s") - np.timedelta64(3600, "s")
    t1 = np.datetime64(start_utc, "s") + np.timedelta64(int(hours * 3600) + 3600, "s")
    sel = (rec.times_utc >= t0) & (rec.times_utc <= t1)
    return _weather(rec, sel, pm_median)


def to_plant_weather(w: Weather, t_bias_k: float = 0.0, ghi_scale: float = 1.0) -> PlantWeather:
    """Hand the same record to the plant; optional truth offsets model forecast bias."""
    ghi = w.ghi_wm2 if w.ghi_wm2 is not None else np.zeros(w.n)
    return PlantWeather(
        times_utc=w.times_utc,
        t_air_c=w.t_air_c + t_bias_k,
        dew_c=w.dew_c + t_bias_k,
        wind10=w.wind10_ms,
        ghi=ghi * ghi_scale,
        pm10=w.pm10_ugm3,
        precip_mm_h=w.precip_mm_h,
        lat=w.lat,
        lon=w.lon,
        altitude_m=w.altitude_m,
        label=w.label,
    )


# ---------------------------------------------------------------------------- scenarios
@dataclass(frozen=True)
class Scenario:
    name: str
    description: str
    micro: bool = True
    shade: str = "none"
    dust0_g_m2: float = 0.0
    foul0_g_m2: float = 0.0
    t_bias_k: float = 0.0
    ghi_scale: float = 1.0
    event_offset_s: float | None = None


SCENARIOS: dict[str, Scenario] = {
    s.name: s
    for s in (
        Scenario(
            "S1",
            "Structure only: minute scale gusts and cloud flicker, no shade, clean robot",
            micro=True,
        ),
        Scenario("S2", "Moving shade: buildings and trees, as S1", shade="urban"),
        Scenario(
            "S3",
            "Soiled robot: 6 g per square metre on the shell, 6 g on the heat sink, as S1",
            dust0_g_m2=6.0,
            foul0_g_m2=6.0,
        ),
        Scenario(
            "S4",
            "Forecast bias: truth 2 K warmer and 10 percent brighter than the record, as S1",
            t_bias_k=2.0,
            ghi_scale=1.10,
        ),
        Scenario("S5", "Dust front 15 minutes into the mission, as S1", event_offset_s=900.0),
    )
}


def hard_limits(profile: Profile) -> np.ndarray:
    return np.array([profile.limits[c].limit_c for c in COMPONENTS])


def allowed_limits(profile: Profile) -> np.ndarray:
    return np.array([profile.limits[c].limit_c - profile.limits[c].margin_k for c in COMPONENTS])


# ---------------------------------------------------------------------------- plant side
def plant_peaks(
    plants: PlantParams,
    w: Weather,
    slot_s: np.ndarray,
    scales: np.ndarray,
    scenario: Scenario,
    seed: int,
    spin_h: float = SPIN_H,
    mission_h: float = 1.0,
    dt: float = 60.0,
    return_soc: bool = False,
):
    """Peak component temperatures (degC) of every plant for every slot: shape (S, P, len(COMPONENTS)).

    ``slot_s`` are mission start times in seconds after the first record time. ``scales`` has one value per
    slot. A scale of zero means the robot stays parked, so the result is the parked peak over the same hour
    (reported, not an operation). With ``return_soc`` the minimum state of charge (S, P) is also returned.
    """
    s_n, p_n = slot_s.size, plants.n
    spin_steps = int(round(spin_h * 3600.0 / dt))
    steps = spin_steps + int(round(mission_h * 3600.0 / dt))
    rng = np.random.default_rng(seed)
    pw = to_plant_weather(w, scenario.t_bias_k, scenario.ghi_scale)
    start = np.repeat(slot_s - spin_h * 3600.0, p_n)
    if start.min() < 0:
        raise ValueError("record does not cover the spin up before the first slot")
    event = None
    if scenario.event_offset_s is not None:
        event = DustEvent(onset_s=spin_h * 3600.0 + scenario.event_offset_s)
    micro = Micro(enabled=scenario.micro, event=event)
    forc = build_forcing(pw, start, steps, dt, rng, micro)
    p_b = plants.tile(s_n)
    drv = build_mission(p_b, np.repeat(scales, p_n), spin_steps, steps, dt, rng)
    drv.shade_beam = build_shade(forc, rng, scenario.shade)
    st = PlantState.at_ambient(
        forc.t_air_c[:, 0], dust=scenario.dust0_g_m2, foul=scenario.foul0_g_m2
    )
    tr = simulate_plant(p_b, forc, drv, st)
    t_c = tr.temps_c()[:, spin_steps:, :]
    peak = np.stack([t_c[:, :, COMPONENT_NODE[c]].max(axis=1) for c in COMPONENTS], axis=1)
    peak = peak.reshape(s_n, p_n, len(COMPONENTS))
    if not return_soc:
        return peak
    soc = tr.soc[:, spin_steps:].min(axis=1).reshape(s_n, p_n)
    return peak, soc


# ---------------------------------------------------------------------------- engine side
@dataclass
class EngineSlots:
    starts: np.ndarray  # engine grid indices
    slot_s: np.ndarray  # seconds after the first record time
    cap: np.ndarray  # perception cap, common to every policy
    scale: dict[str, np.ndarray]  # P1 to P5
    risk_peak: np.ndarray  # (S, 5) risk quantile peak at the P4 scale, no offset
    allowed: np.ndarray
    reserve: float


def engine_slots(
    profile: Profile,
    w: Weather,
    first_utc: str,
    last_utc: str,
    seed: int,
    offsets_k: tuple[float, ...] | None = None,
    mission_h: float = 1.0,
) -> EngineSlots:
    """Engine decisions for every hourly slot under policies P1 to P5 (the oracle P6 needs the plant)."""
    cfg = EngineConfig(n_mc=64, seed=seed)
    env = Envelope(profile, w, cfg)
    starts = slot_starts(env, first_utc, last_utc)
    cap, _, _ = env.perception_cap(starts, mission_h)
    s4, _ = env.best_scale(starts, mission_h, "drive")
    env0 = Envelope(profile, w, replace(cfg, sigma_scale=0.0))
    s3, _ = env0.best_scale(starts, mission_h, "drive")
    s2 = ambient_threshold(env, starts, mission_h, 35.0) * cap
    scales = {"P1": cap.copy(), "P2": s2, "P3": s3, "P4": s4}
    if offsets_k is not None:
        env5 = Envelope(profile, w, replace(cfg, quantile_offset_k=tuple(offsets_k)))
        scales["P5"], _ = env5.best_scale(starts, mission_h, "drive")
    else:
        scales["P5"] = s4.copy()
    scan = env.scan(
        starts, np.maximum(s4, profile.operations.min_scale)[:, None], mission_h, "drive"
    )
    return EngineSlots(
        starts=starts,
        slot_s=starts * cfg.dt_s,
        cap=cap,
        scale=scales,
        risk_peak=scan["risk_peak_c"][:, 0, :],
        allowed=allowed_limits(profile),
        reserve=profile.operations.soc_reserve,
    )


# ---------------------------------------------------------------------------- scoring
@dataclass
class ClassDay:
    """Plant outcomes of one robot class on one day for one scenario (S slots, P robots)."""

    scales: dict[str, np.ndarray]  # P1 to P6; P6 has shape (S, P), the others (S,)
    breach: dict[str, np.ndarray]  # (S, P) bool, only meaningful where the scale is above zero
    hard: dict[str, np.ndarray]  # (S, P) bool, hard limit exceeded
    peak_p4: np.ndarray  # (S, P, 5) plant peaks at the P4 scale
    risk_peak: np.ndarray  # (S, 5)


def _outcome(profile: Profile, peak: np.ndarray, soc: np.ndarray):
    breach = (peak > allowed_limits(profile)[None, None, :]).any(axis=2)
    breach |= soc < profile.operations.soc_reserve
    hard = (peak > hard_limits(profile)[None, None, :]).any(axis=2)
    return breach, hard


def run_class_day(
    profile: Profile,
    plants: PlantParams,
    w: Weather,
    es: EngineSlots,
    scenario: Scenario,
    seed: int,
) -> ClassDay:
    """Run the plant at every policy's scales and on the oracle grid."""
    scales: dict[str, np.ndarray] = {}
    breach: dict[str, np.ndarray] = {}
    hard: dict[str, np.ndarray] = {}
    cache: dict[bytes, tuple] = {}

    def run(sc: np.ndarray):
        key = np.round(sc, 6).tobytes()
        if key not in cache:
            cache[key] = plant_peaks(plants, w, es.slot_s, sc, scenario, seed, return_soc=True)
        return cache[key]

    peak4 = None
    for pol in ("P1", "P2", "P3", "P4", "P5"):
        sc = es.scale[pol]
        peak, soc = run(sc)
        breach[pol], hard[pol] = _outcome(profile, peak, soc)
        scales[pol] = sc
        if pol == "P4":
            peak4 = peak
    # oracle: largest grid scale (clipped by the perception cap) without a breach, per robot
    best = np.zeros((es.slot_s.size, plants.n))
    for g in SCALE_GRID[1:]:
        sc = np.minimum(g, es.cap)
        peak, soc = run(sc)
        b, _ = _outcome(profile, peak, soc)
        best = np.where(~b, np.maximum(best, sc[:, None]), best)
    scales["P6"] = best
    breach["P6"] = np.zeros_like(breach["P4"])
    hard["P6"] = np.zeros_like(hard["P4"])
    assert peak4 is not None
    return ClassDay(scales, breach, hard, peak4, es.risk_peak)


def conformal_level(n: int, alpha: float = 0.05) -> float:
    """Quantile level ceil((n + 1) (1 - alpha)) / n for split conformal prediction, capped at 1."""
    return min(1.0, float(np.ceil((n + 1) * (1.0 - alpha))) / n)


def conformal_offset(scores: np.ndarray, alpha: float = 0.05) -> float:
    """Split conformal offset: the k-th smallest score with k = ceil((n + 1) (1 - alpha)).

    When k exceeds n the largest score is returned, so the guarantee then holds only approximately.
    """
    scores = np.sort(np.asarray(scores, dtype=float))
    if scores.size == 0:
        raise ValueError("no scores")
    k = int(np.ceil((scores.size + 1) * (1.0 - alpha)))
    return float(scores[min(k, scores.size) - 1])


# ---------------------------------------------------------------------------- field records
def field_record(
    plant: PlantParams,
    rec: SiteRecord,
    start_utc: str,
    hours: float,
    seed: int,
    scenario: Scenario | None = None,
    spec=None,
    station_noise: bool = True,
):
    """One logging record from one plant robot: telemetry as a logger would write it, and station weather.

    Returns ``(Telemetry, Weather, truth_c)``. The robot starts at ambient, drives 35 minutes of each hour
    between 06:00 and 20:00 local time, and is parked otherwise.
    """
    from .calibrate import LOAD_COLS, Telemetry
    from .plant.sensors import SensorSpec
    from .plant.sensors import measure as _measure

    scenario = scenario or SCENARIOS["S1"]
    spec = spec or SensorSpec()
    dt = 60.0
    steps = int(hours * 3600.0 / dt)
    w_hour = span_weather(rec, start_utc, hours)
    pw = to_plant_weather(w_hour, scenario.t_bias_k, scenario.ghi_scale)
    rng = np.random.default_rng(seed)
    start_s = np.array([float((np.datetime64(start_utc, "s") - w_hour.times_utc[0]).astype(float))])
    forc = build_forcing(pw, start_s, steps, dt, rng, Micro(enabled=scenario.micro))
    local_hour = (np.datetime64(start_utc, "s") - np.datetime64(start_utc, "D")).astype(
        float
    ) / 3600.0 + LOCAL_OFFSET_H
    sched = field_schedule(1, steps, dt, local_hour, rng)
    drv = build_mission(plant, sched, 0, steps, dt, rng)
    drv.shade_beam = build_shade(forc, rng, scenario.shade)
    st = PlantState.at_ambient(
        forc.t_air_c[:, 0], dust=scenario.dust0_g_m2, foul=scenario.foul0_g_m2
    )
    tr = simulate_plant(plant, forc, drv, st)
    r = _measure(tr, drv, 0, rng, spec)
    t0 = np.datetime64(start_utc, "s")
    times = t0 + r.seconds.astype("timedelta64[s]")
    tel = Telemetry(times, {k: r.loads[k] for k in LOAD_COLS}, r.temps_c)
    # station weather every ten minutes with instrument noise; the last point repeats the final value
    stride = 10
    idx = np.append(np.arange(0, steps, stride), steps - 1)
    secs = np.append(np.arange(0, steps, stride) * dt, steps * dt)
    ghi_true = forc.ghi[0, idx]
    noise = (
        (lambda s: rng.standard_normal(idx.size) * s)
        if station_noise
        else (lambda s: np.zeros(idx.size))
    )
    w_st = Weather(
        times_utc=t0 + secs.astype("timedelta64[s]"),
        t_air_c=forc.t_air_c[0, idx] + noise(0.2),
        dew_c=np.minimum(forc.dew_c[0, idx], forc.t_air_c[0, idx] - 0.1),
        wind10_ms=np.maximum(forc.wind10[0, idx] * (1.0 + noise(0.10)), 0.0),
        pm10_ugm3=np.maximum(forc.pm10[0, idx] * (1.0 + noise(0.15)), 0.0),
        precip_mm_h=forc.rain_mm_h[0, idx],
        lat=rec.site.lat,
        lon=rec.site.lon,
        altitude_m=rec.site.altitude_m,
        ghi_wm2=np.maximum(ghi_true * (1.0 + noise(0.02)), 0.0),
        source="synthetic on site station (from plant forcing)",
        label=rec.site.id,
    )
    return tel, w_st, r.truth_c
